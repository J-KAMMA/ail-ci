"""GPU stage G5 (docs/design/GPU.md 6.3): correctly rounded binary64 `/` and `math.sqrt` in SPIR-V.

Two layers:

* `SpirvG5`   -- the emitter alone: no OpFDiv (136) and no Fma, every FAdd/FSub/FMul carries NoContraction, no
                 fast-math decoration, and the module is SPIR-V 1.4 with the binary64 capabilities.  Runs in any shard.
* `BitTests`  -- GPU.md 5.1: one kernel applies `/` (and one `sqrt`) to 131,072 operand pairs (random bit patterns,
                 +-0, subnormals, the smallest and largest normals, 1 +- ulp, powers of two, halfway constructions,
                 NaN and inf) and the C side compares every result bit with the CPU's own `double` op.  Needs a
                 Vulkan device (lavapipe in the `gpu` job; skipped in the shards).
* `Programs`  -- whole `--gpu` builds that use `/` and `math.sqrt`: stdout and exit status equal CPython's and the
                 same binary's `AIL_GPU=0` run, and `AIL_GPU_TRACE` shows the kernel ran on the device.
"""
import ast
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent
PKG = ROOT / 'python' / 'pkg-v12'
if str(PKG) not in sys.path:
    sys.path.insert(0, str(PKG))

CLI = ROOT / 'ail_chatgpt.py'
CC = shutil.which('cc') or shutil.which('gcc') or shutil.which('clang')
REQUIRE_DEVICE = os.environ.get('AIL_GPU_REQUIRE_DEVICE', '') not in ('', '0')
SPIRV_VAL = os.environ.get('SPIRV_VAL') or shutil.which('spirv-val')


def kernel_of(src, types):
    """The kernel IR of the last statement of `src` (a comprehension), typed by `types`."""
    import gpu
    tree = ast.parse(src)
    funcs = gpu._funcs_of(tree)
    stmt = [n for n in tree.body if not isinstance(n, ast.FunctionDef)][-1]
    site = gpu._classify(stmt, funcs)
    site['k'] = 0

    def oracle(what, name, node):
        return types[name]
    builder = gpu.Builder(site, funcs, oracle)
    return builder.build_for() if site['kind'] == 'for' else builder.build_comp()


def comp(expr, names='x, y', lists='a, b'):
    source = lists if ',' not in lists else 'zip(%s)' % lists
    return 'import math\nr = [%s for %s in %s]\n' % (expr, names, source)


FF = {'a': 'f', 'b': 'f'}
F1 = {'a': 'f'}
ENTRIES = [('f_div', comp('x / y'), FF), ('f_sqrt', comp('math.sqrt(x)', 'x', 'a'), F1)]


class SpirvG5(unittest.TestCase):
    """The emitter alone: the exactness rules of GPU.md 3.2 hold for the two new ops."""

    @classmethod
    def setUpClass(cls):
        import gpu_spirv
        cls.sp = gpu_spirv
        cls.mods = {name: cls.sp.compile_kernel(kernel_of(src, types)) for name, src, types in ENTRIES}

    @staticmethod
    def instructions(words):
        i = 5
        while i < len(words):
            n = words[i] >> 16
            yield words[i] & 0xFFFF, words[i + 1:i + n]
            i += n

    def test_header_and_capabilities(self):
        for name, (words, info) in self.mods.items():
            self.assertEqual(words[0], 0x07230203, name)
            self.assertEqual(words[1], 0x00010400, name)                 # SPIR-V 1.4 (Vulkan 1.2)
            caps = [ops[0] for op, ops in self.instructions(words) if op == 17]
            self.assertTrue({1, 10, 11, 4467, 4466} <= set(caps), '%s: %r' % (name, caps))
            self.assertTrue(info['need_f64'], name)

    def test_no_division_instruction_and_no_fma(self):
        for name, (words, _) in self.mods.items():
            for op, _ops in self.instructions(words):
                self.assertNotEqual(op, 136, '%s: OpFDiv' % name)          # OpFDiv
                self.assertNotIn(op, (50, 51), name)                       # no OpFma-shaped instruction
                # GLSL ExtInst: FAbs 4, Floor 8, Ceil 9, Sqrt 31 are the only ones this stage may add
                if op == 12:
                    self.assertIn(_ops[3], (4, 8, 9, 31), '%s: ext inst %d' % (name, _ops[3]))

    def test_every_float_arithmetic_op_is_not_contractable(self):
        for name, (words, _) in self.mods.items():
            decorated = {}
            for op, ops in self.instructions(words):
                if op == 71:
                    decorated.setdefault(ops[0], set()).add(ops[1])
                    self.assertNotEqual(ops[1], 40, '%s: FPFastMathMode' % name)
            seen = 0
            for op, ops in self.instructions(words):
                if op in (129, 131, 133):                                  # FAdd, FSub, FMul
                    seen += 1
                    self.assertIn(42, decorated.get(ops[1], ()), '%s: float op %d lacks NoContraction' % (name, ops[1]))
            self.assertGreater(seen, 20, name)                             # the residual arithmetic is really there

    def test_every_kernel_validates(self):
        if not SPIRV_VAL:
            raise unittest.SkipTest('spirv-val not installed (apt install spirv-tools)')
        import struct
        with tempfile.TemporaryDirectory(prefix='ail-spv-g5-') as d:
            for name, (words, _) in self.mods.items():
                path = Path(d) / (name + '.spv')
                path.write_bytes(struct.pack('<%dI' % len(words), *words))
                r = subprocess.run([SPIRV_VAL, '--target-env', 'vulkan1.2', str(path)], capture_output=True, text=True)
                self.assertEqual(r.returncode, 0, '%s:\n%s' % (name, r.stdout + r.stderr))


# ---------------------------------------------------------------------------------------------------------------------
HARNESS = r'''
#include <stdio.h>
#include <stdlib.h>
#include <stdint.h>
#include <string.h>
#include <math.h>
%(runtime)s
%(kernels)s
static uint64_t rs = 88172645463325252ull;
static uint64_t rnd(void) { rs ^= rs << 13; rs ^= rs >> 7; rs ^= rs << 17; return rs; }
static double d_of(uint64_t b) { double d; memcpy(&d, &b, 8); return d; }
static uint64_t b_of(const void *p) { uint64_t b; memcpy(&b, p, 8); return b; }
static const double EDGE_F[] = { 0.0, -0.0, 1.0, -1.0, 0.5, 2.0, 1.5, 3.0, 0.1, 1e300, -1e300, 1.7976931348623157e308,
    -1.7976931348623157e308, 2.2250738585072014e-308, 4.9406564584124654e-324, 1e-310, -1e-310, 9.332636185032189e-302,
    9.3326361850321887e-302, 1e-300, -1e-300, 4503599627370496.0, 4503599627370497.5, 9007199254740992.0,
    9007199254740993.0, 1e-160, 1e160, 9.999999999999999e-161, 123456789.123, 0.30000000000000004,
    0.0 / 0.0, 1.0 / 0.0, -1.0 / 0.0, 2.2250738585072014e-308, 1.1125369292536007e-308, 2.0, 4.0, 16.0, 0.25 };
#define NEF ((int)(sizeof EDGE_F / sizeof EDGE_F[0]))
static double rand_f(void) {
    switch (rnd() %% 8) {
    case 0: case 1: return d_of(rnd());
    case 2: case 3: return EDGE_F[rnd() %% NEF];
    case 4: { uint64_t e = rnd() %% 2047; return d_of((rnd() & 0x800fffffffffffffull) | (e << 52)); }
    case 5: return (double)((int64_t)(rnd() %% 201) - 100);
    case 6: return d_of((rnd() & 0x800fffffffffffffull) | ((1023 - 30 + rnd() %% 60) << 52));
    default: return d_of((rnd() & 0x800fffffffffffffull) | ((1 + rnd() %% 2046) << 52));
    }
}
static double rand_near(double a) {
    switch (rnd() %% 6) {
    case 0: return a;
    case 1: return -a;
    case 2: return d_of(b_of(&a) + (rnd() %% 5));
    case 3: return d_of(b_of(&a) - (rnd() %% 5));
    case 4: return a * 0.5;
    default: return rand_f();
    }
}
#define N %(n)d
static double Af[N], Bf[N];
static int mismatches = 0;
%(runs)s
int main(void) {
    for (int i = 0; i < N; i++) { Af[i] = rand_f(); Bf[i] = rand_near(Af[i]); }
    setenv("AIL_GPU", "force", 1);
    %(calls)s
    printf("DONE mismatches=%%d device=%%s\n", mismatches, gk_dev);
    return 0;
}
'''

RUN = r'''
static void run_%(name)s(void) {
    static unsigned ef[N]; static double ev[N];
    int clean = 0, flagged = 0, checked = 0, bad = 0, missed = 0, spurious = 0;
    %(decls)s
    double *dres = malloc((size_t)N * sizeof(double));
    for (int i = 0; i < N; i++) {
        ef[i] = %(emu)s(%(one)s);
        if (ef[i] == 0) { %(pack)s clean++; } else flagged++;
    }
    if (clean > 0) {
        unsigned f = %(run)s(%(pk)s);
        if (strcmp(gk_dev, "emulation") == 0) { printf("NODEVICE %(name)s\n"); exit(77); }
        if (f != 0) spurious++;
        else {
            int j = 0;
            for (int i = 0; i < N; i++) if (ef[i] == 0) {
                if (memcmp(&dres[j], &ev[i], 8) != 0) {
                    if (bad < 5) printf("  differs at %%d: a=%%016llx b=%%016llx dev=%%016llx cpu=%%016llx\n",
                                        i, (unsigned long long)b_of(&Af[i]), (unsigned long long)b_of(&Bf[i]),
                                        (unsigned long long)b_of(&dres[j]), (unsigned long long)b_of(&ev[i]));
                    bad++;
                }
                j++;
            }
        }
    }
    for (int i = 0; i < N && checked < 400; i++) if (ef[i] != 0) {
        double tmp = 0;
        unsigned f = %(emu)s(%(one_tmp)s);
        if (f == 0) { missed++; if (missed < 5) printf("  missed flag %%u at %%d\n", ef[i], i); }
        checked++;
    }
    printf("K %(name)s clean=%%d flagged=%%d checked=%%d bad=%%d spurious=%%d missed=%%d\n",
           clean, flagged, checked, bad, spurious, missed);
    mismatches += bad + spurious + missed;
    free(dres);
}
'''


def harness(entries, n):
    import gpu
    import gpu_vk
    kernels, runs, calls = [], [], []
    for idx, (name, src, types) in enumerate(entries):
        k = kernel_of(src, types)
        fname = 'ail_gk%d' % idx
        kernels.append(gpu.emit_c(k, fname))
        dev_c, info, words = gpu_vk.device_text(k, fname, idx)
        kernels.append(gpu_vk.VK_RUNTIME + dev_c)
        names = gpu.emu_signature(k)[1]
        one, pk, one_tmp, decls, pack = [], [], [], [], []
        for nm in names:
            if nm.startswith('p_'):
                a = {'a': 'Af', 'b': 'Bf'}[nm[2:]]
                one.append('%s + i' % a)
                one_tmp.append('%s + i' % a)
                pk.append('pk_%s' % a)
                if 'pk_%s' % a not in ' '.join(decls):
                    decls.append('double *pk_%s = malloc((size_t)N * sizeof(double));' % a)
                    pack.append('pk_%s[clean] = %s[i];' % (a, a))
            elif nm.startswith('n_'):
                one.append('1')
                one_tmp.append('1')
                pk.append('clean')
            elif nm == '_cnt':
                one.append('1')
                one_tmp.append('1')
                pk.append('clean')
            elif nm == '_res':
                one.append('&ev[i]')
                one_tmp.append('&tmp')
                pk.append('dres')
            else:
                raise AssertionError(nm)
        runs.append(RUN % dict(name=name, emu=fname, run=fname + '_run', one=', '.join(one),
                               one_tmp=', '.join(one_tmp), pk=', '.join(pk),
                               decls=' '.join(decls), pack=' '.join(pack)))
        calls.append('run_%s();' % name)
    return HARNESS % dict(runtime=gpu.RUNTIME, kernels='\n'.join(kernels), n=n, runs='\n'.join(runs),
                          calls='\n    '.join(calls))


def device_env():
    env = dict(os.environ)
    for key in ('AIL_GPU', 'AIL_GPU_TRACE', 'AIL_GPU_DISABLE', 'AIL_VULKAN_LIB', 'AIL_GPU_DEVICE', 'AIL_GPU_MIN_N'):
        env.pop(key, None)
    return env


class BitTests(unittest.TestCase):
    """GPU.md 5.1: the device against the CPU's own `/` and sqrt, bit for bit."""

    N = 131072

    @classmethod
    def setUpClass(cls):
        if not CC:
            raise unittest.SkipTest('no C compiler')
        cls._tmp = tempfile.TemporaryDirectory(prefix='ail-gpu5-bits-')
        cls.dir = Path(cls._tmp.name)

    @classmethod
    def tearDownClass(cls):
        cls._tmp.cleanup()

    def test_division_and_sqrt_bits(self):
        src = self.dir / 'bits.c'
        src.write_text(harness(ENTRIES, self.N), encoding='utf-8')
        exe = self.dir / 'bits'
        r = subprocess.run([CC, '-O1', '-std=gnu11', '-w', str(src), '-o', str(exe), '-lm', '-ldl'],
                           capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stderr[:3000])
        r = subprocess.run([str(exe)], capture_output=True, text=True, env=device_env(), timeout=900)
        if r.returncode == 77:
            if REQUIRE_DEVICE:
                self.fail('no Vulkan device, but AIL_GPU_REQUIRE_DEVICE is set:\n' + r.stdout)
            raise unittest.SkipTest('no Vulkan device (install mesa-vulkan-drivers for lavapipe)')
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        lines = {m[1]: m for m in (re.match(r'K (\S+) clean=(\d+) flagged=(\d+) checked=(\d+) bad=(\d+) spurious=(\d+) missed=(\d+)', l)
                                   for l in r.stdout.splitlines()) if m}
        for name, _, _ in ENTRIES:
            self.assertIn(name, lines, r.stdout)
            _, clean, flagged, checked, bad, spurious, missed = lines[name].groups()
            self.assertEqual((int(bad), int(spurious), int(missed)), (0, 0, 0), r.stdout)
            self.assertGreater(int(clean), 100000 // 2, '%s: too few clean elements\n%s' % (name, r.stdout))
        self.assertIn('DONE mismatches=0', r.stdout)


# ---------------------------------------------------------------------------------------------------------------------
def trace_of(stderr):
    return [l for l in stderr.splitlines() if l.startswith('gpu: ')]


class Programs(unittest.TestCase):
    """Whole `--gpu` builds: CPython, AIL_GPU=0 and the device print the same, and the trace names the device."""

    @classmethod
    def setUpClass(cls):
        cls._tmp = tempfile.TemporaryDirectory(prefix='ail-gpu5-progs-')
        cls.dir = Path(cls._tmp.name)

    @classmethod
    def tearDownClass(cls):
        cls._tmp.cleanup()

    CASES = [
        ('div_float', '''
import math
n = 8192
a = [0.0] * n
b = [0.0] * n
for i in range(n):
    a[i] = float(i) * 0.5 - 1000.0
    b[i] = float(i % 37) / 8.0 + 0.25
out = [0.0] * n
# ail: gpu
for i in range(n):
    out[i] = a[i] / b[i]
print(out[0], out[1024], out[4095], out[8191])
'''),
        ('div_int_and_mixed', '''
n = 8192
a = [0] * n
b = [0] * n
for i in range(n):
    a[i] = i * 7 - 4000
    b[i] = (i % 13) + 1
out = [0.0] * n
# ail: gpu
for i in range(n):
    out[i] = a[i] / b[i] + float(a[i]) / 3.0
print(out[0], out[1024], out[4095], out[8191])
'''),
        ('sqrt_float', '''
import math
n = 8192
a = [0.0] * n
for i in range(n):
    a[i] = float(i) * 0.5 + 1.0
out = [0.0] * n
# ail: gpu
for i in range(n):
    out[i] = math.sqrt(a[i])
print(out[0], out[1024], out[4095], out[8191])
'''),
        ('sqrt_expr', '''
import math
n = 8192
a = [0.0] * n
b = [0.0] * n
for i in range(n):
    a[i] = float(i) + 2.0
    b[i] = float(i % 7) + 1.0
out = [0.0] * n
# ail: gpu
for i in range(n):
    out[i] = math.sqrt(a[i] * b[i]) + a[i] / b[i]
print(out[0], out[1024], out[4095], out[8191])
'''),
    ]

    def build(self, name, text):
        src = self.dir / (name + '.py')
        src.write_text(text.lstrip('\n'), encoding='utf-8')
        exe = self.dir / (name + '.exe')
        env = device_env()
        env.update(AIL_NO_CACHE='1')
        for key in ('AIL_GPU_BUILD', 'AIL_UNIFIED_FORCE'):
            env.pop(key, None)
        r = subprocess.run([sys.executable, '-B', str(CLI), 'compile', str(src), '-o', str(exe), '--no-cache',
                            '--gpu', '--debug-dir', str(self.dir / (name + '.dbg'))],
                           capture_output=True, text=True, env=env, timeout=900)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        return src, exe, r.stderr

    def run_prog(self, exe, **env):
        e = device_env()
        e.update(env)
        r = subprocess.run([str(exe)], capture_output=True, text=True, env=e, timeout=600)
        return r.stdout, r.returncode, r.stderr

    def test_programs_match_cpython_and_the_device_runs_them(self):
        for name, text in self.CASES:
            with self.subTest(name):
                src, exe, build_err = self.build(name, text)
                py = subprocess.run([sys.executable, '-B', str(src)], capture_output=True, text=True)
                self.assertEqual(py.returncode, 0, py.stderr)
                zero = self.run_prog(exe, AIL_GPU='0')
                self.assertEqual((zero[0], zero[1]), (py.stdout, py.returncode), 'AIL_GPU=0')
                dev = self.run_prog(exe, AIL_GPU='force', AIL_GPU_TRACE='1')
                self.assertEqual((dev[0], dev[1]), (py.stdout, py.returncode), 'device')
                ran = [l for l in trace_of(dev[2]) if re.match(r'gpu: k\d+ n=\d+ device=', l)]
                if REQUIRE_DEVICE:
                    self.assertTrue(ran, 'no launch on the device:\n' + dev[2])
                    self.assertNotIn('device=emulation', ' '.join(ran), dev[2])
                elif not ran:
                    raise unittest.SkipTest('no Vulkan device')


if __name__ == '__main__':
    unittest.main()
