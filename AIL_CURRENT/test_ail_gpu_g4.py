"""GPU stage G4 (docs/design/GPU.md 6.4): a launch that is not clearly worth it runs the ORIGINAL loop.

G3 measured the Radeon 780M: one launch costs about 4.5 ms, the device wins only for arithmetic-heavy kernels on large
inputs, and a launch that is not sent to the device ran the G1 emulation, 1.2x to 16x slower than the plain loop.  G4:

* the kernel wrapper has a third answer, `GK_DECLINED`; the glue then runs the original typed loop (not the emulation).
  The emulation only runs for `AIL_GPU=emu` and inside the self-test and the first-launch comparison; a device launch that
  flags still replays the original loop;
* `AIL_GPU=auto` (the default of a `--gpu` build): `ail_gk<k>_want` decides before anything is allocated, from the
  kernel's operation count and the sizes, with the cost model of `gpu_vk.py` (t_cpu >= 1.5 t_dev), a software device is
  never used, and the device's cold start must have been earned back by the launches that were declined;
* `AIL_GPU_MIN_N=<n>` still overrides the model with "the device from n elements".

What these tests check: the ops count of the emitter; the cost model on the cells of the 780M table; at the C level that a
declined launch calls the emulation zero times; and that every mode (off, emu, force, auto declined, auto on the device,
auto with a flagged launch, no loader, untrusted device) prints the same stdout and exit code as CPython.
"""
import os
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent
PKG = ROOT / 'python' / 'pkg-v12'
for p in (str(ROOT), str(PKG)):
    if p not in sys.path:
        sys.path.insert(0, p)

import test_ail_gpu_g2 as g2                                    # noqa: E402  (helpers only; its test classes stay there)

CC = g2.CC
REQUIRE_DEVICE = g2.REQUIRE_DEVICE
NEW_KEYS = ('AIL_GPU_MODEL', 'AIL_GPU_AUTO_ANY', 'AIL_GPU_INJECT', 'AIL_GPU_CHECK')


def _env(**extra):
    env = g2._device_env()
    for key in NEW_KEYS:
        env.pop(key, None)
    env.update(extra)
    return env


# ---------------------------------------------------------------------------------------------------------------------
def ops_of(src, types, scalars=None, **names):
    """The value of the kernel's `ops_expr` (a C expression over s_* and n_*) for the given values."""
    import gpu
    k = g2.kernel_of(src, types, scalars)
    expr = gpu.ops_expr(k).replace('(double)', '')
    env = dict(gkv_max=max, gkv_trip=lambda lo, hi: max(hi - lo, 0.0))
    env.update(names)
    return eval(expr, {'__builtins__': {}}, env)


class Ops(unittest.TestCase):
    """GPU.md 6.4: the per-element operation count the cost model uses (the G3 fit was made with these counts)."""

    def test_the_g3_kernels(self):
        # light: (x + y) * (x - y) + x * 0.1 = 5 operations plus the store
        self.assertEqual(ops_of(g2.comp('(x + y) * (x - y) + x * 0.1'), g2.FF), 6)
        heavy = ('out = [0.0] * 8\nfor i in range(8):\n    acc = 0.0\n    for j in range(64):\n'
                 '        acc = acc + a[i] * 0.5 - acc * 0.001\n    out[i] = acc\n')
        self.assertEqual(ops_of(heavy, {'a': 'f'}), 64 * 5 + 1)           # 64 steps of 5 operations
        ints = g2.comp('(x + y) // 3 + x * y - z', 'x, y, z', 'a, b, c')
        self.assertEqual(ops_of(ints, {'a': 'i', 'b': 'i', 'c': 'i'}), 6)

    def test_a_loop_bound_that_is_a_scalar_or_a_length(self):
        body = 'out = [0.0] * 8\nfor i in range(8):\n    acc = 0.0\n    for j in range(%s):\n        acc = acc + a[i]\n    out[i] = acc\n'
        self.assertEqual(ops_of(body % 'k', {'a': 'f'}, {'k': 'i'}, s_k=10.0), 10 * 2 + 1)
        self.assertEqual(ops_of(body % 'len(a)', {'a': 'f'}, None, n_a=7.0), 7 * 2 + 1)
        # a bound the counter cannot read counts the body once: fewer ops, so the model declines more (never launches more)
        self.assertEqual(ops_of(body % 'k // 2', {'a': 'f'}, {'k': 'i'}, s_k=10.0), 1 * 2 + 1)

    def test_a_branch_counts_its_dearer_side(self):
        src = ('out = [0.0] * 8\nfor i in range(8):\n    y = a[i]\n    if y > 1.0:\n        y = y * 2.0 + 1.0 - y\n'
               '    else:\n        y = y + 1.0\n    out[i] = y\n')
        both = ops_of(src, {'a': 'f'})
        one = ops_of(src.replace('y = y * 2.0 + 1.0 - y', 'y = y + 1.0 + 0.0'), {'a': 'f'})
        self.assertEqual(both - one, 1)                      # the dearer side has one more operation, and only it counts

    def test_the_wrapper_asks_before_it_allocates(self):
        import gpu
        import gpu_vk
        k = g2.kernel_of(g2.comp('x - y'), g2.FF)
        text, info, words = gpu_vk.device_text(k, 'ail_gk0', 0, gpu.ops_expr(k))
        for needle in ('static int ail_gk0_want(', 'gkv_decide(0,', 'return GK_DECLINED;', 'ail_gk0_dec'):
            self.assertIn(needle, text)
        self.assertNotIn('goto emu', text)                       # the fallback is the original loop, not the emulation


# ---------------------------------------------------------------------------------------------------------------------
MODEL_MAIN = r'''
#include <stdio.h>
#include <stdlib.h>
#include <stdint.h>
#include <string.h>
#include <math.h>
%(runtime)s
int main(void) {
    static const struct { const char *name; double ops; double lists; int64_t n; } C[] = {
        %(cells)s
    };
    for (unsigned i = 0; i < sizeof C / sizeof C[0]; i++) {
        double tc, td;
        int w = gkv_model_win(C[i].n, 8.0 * C[i].n * (C[i].lists + 1.0), C[i].ops, &tc, &td);
        printf("%%s n=%%lld win=%%d tc=%%.1f td=%%.1f\n", C[i].name, (long long)C[i].n, w, tc, td);
    }
    return 0;
}
'''

SIZES = (4096, 16384, 65536, 262144, 1000000, 10000000)


class Model(unittest.TestCase):
    """The cost model on the cells of the G3 table (Radeon 780M): where it must decline and where it may launch."""

    @classmethod
    def setUpClass(cls):
        if not CC:
            raise unittest.SkipTest('no C compiler')
        import gpu
        import gpu_vk
        cls._tmp = tempfile.TemporaryDirectory(prefix='ail-gpu4-model-')
        cls.dir = Path(cls._tmp.name)

        def cells(spec):
            return ' '.join('{ "%s", %d, %d, %d },' % (name, ops, lists, n) for name, ops, lists, n, reps in spec
                            for _ in range(reps))
        every = [(name, ops, lists, n, 1) for name, ops, lists in (('light', 6, 2), ('heavy', 321, 1), ('int64', 6, 3)) for n in SIZES]
        progs = (('one', every), ('cold1m', [('heavy', 321, 1, 1000000, 14), ('heavy', 321, 1, 10000000, 2)]),
                 ('cold10m', [('heavy', 321, 1, 10000000, 1)]))
        for tag, spec in progs:
            src = cls.dir / (tag + '.c')
            src.write_text(MODEL_MAIN % dict(runtime=gpu.RUNTIME + gpu_vk.VK_RUNTIME, cells=cells(spec)), encoding='utf-8')
            r = subprocess.run([CC, '-O1', '-std=gnu11', '-w', str(src), '-o', str(cls.dir / tag), '-lm', '-ldl'],
                               capture_output=True, text=True)
            if r.returncode != 0:
                raise AssertionError(r.stderr[:3000])

    @classmethod
    def tearDownClass(cls):
        cls._tmp.cleanup()

    def table(self, tag, **env):
        r = subprocess.run([str(self.dir / tag)], capture_output=True, text=True, env=_env(**env), timeout=60)
        self.assertEqual(r.returncode, 0, r.stderr)
        rows = []
        for line in r.stdout.splitlines():
            m = re.match(r'(\w+) n=(\d+) win=(-?\d) tc=([\d.]+) td=([\d.]+)', line)
            rows.append((m[1], int(m[2]), int(m[3]), float(m[4]), float(m[5])))
        return rows

    def test_decisions_without_the_cold_start(self):
        """AIL_GPU_MODEL's last field (the cold start) = 0 isolates the size/ops rule."""
        got = {(k, n): w for k, n, w, _, _ in self.table('one', AIL_GPU_MODEL='300,0.17,0.06,0.20,1.5,0')}
        for n in SIZES:
            self.assertEqual(got['light', n], 0, ('light', n))          # 6 ops: the device loses at every size (G3, G4)
            self.assertEqual(got['int64', n], 0, ('int64', n))          # int64: loses at every size (G3, G4)
        self.assertEqual(got['heavy', 4096], 0)                         # 4,096 was a tie in G4 (0.32 ms against 0.40 ms)
        for n in (65536, 262144, 1000000, 10000000):
            self.assertEqual(got['heavy', n], 1, ('heavy', n))          # 3.7x, 2.3x, 4.3x and 6.5x faster in G4

    def test_the_margin_is_in_the_rule(self):
        for _, n, w, tc, td in self.table('one', AIL_GPU_MODEL='300,0.17,0.06,0.20,1.5,0'):
            self.assertEqual(w == 1, tc >= 1.5 * td, (n, tc, td))

    def test_the_cold_start_has_to_be_earned_back(self):
        """With the default cold start (0.3 s) a heavy 1M launch (predicted saving about 40 ms) is declined until the
        declined launches would have saved that much; a launch that saves more than the cold start goes at once."""
        rows = self.table('cold1m')
        heavy_1m = [w for k, n, w, _, _ in rows if n == 1000000]
        self.assertEqual(heavy_1m[0], -1, heavy_1m)
        self.assertIn(1, heavy_1m, heavy_1m)
        first = heavy_1m.index(1)
        self.assertTrue(all(w == -1 for w in heavy_1m[:first]), heavy_1m)
        self.assertGreaterEqual(first, 3, heavy_1m)
        self.assertTrue(all(w == 1 for w in heavy_1m[first:]), heavy_1m)
        # the credit is process-wide, and a launch that saves more than the cold start goes at once
        self.assertTrue(all(w == 1 for k, n, w, _, _ in rows if n == 10000000))
        self.assertEqual([w for k, n, w, _, _ in self.table('cold10m')], [1])

    def test_strict_mode_never_lets_a_program_lose_the_cold_start(self):
        """AIL_GPU_STRICT=1: no accumulation, only a single launch that saves more than the cold start goes."""
        rows = self.table('cold1m', AIL_GPU_STRICT='1')
        self.assertEqual({w for k, n, w, _, _ in rows if n == 1000000}, {-1})          # saves 40 ms each: never
        self.assertEqual({w for k, n, w, _, _ in rows if n == 10000000}, {1})          # saves 0.4 s: goes
        self.assertEqual([w for k, n, w, _, _ in self.table('cold10m', AIL_GPU_STRICT='1')], [1])


# ---------------------------------------------------------------------------------------------------------------------
DECLINE_MAIN = r'''
#include <stdio.h>
#include <stdlib.h>
#include <stdint.h>
#include <string.h>
#include <math.h>
%(runtime)s
static int emu_calls;
%(kernels)s
int main(void) {
    enum { N = 10000 };
    static double a[N], b[N], r[N];
    for (int i = 0; i < N; i++) { a[i] = i * 0.5; b[i] = i * 0.25; }
    int w = ail_gk0_want(a, N, b, N, N);
    unsigned f = ail_gk0_run(a, N, b, N, N, r);
    printf("want=%%d flag=%%s calls=%%d dev=%%s r5=%%.17g\n", w, f == GK_DECLINED ? "declined" : f ? "flagged" : "ok", emu_calls, gk_dev, r[5]);
    return 0;
}
'''


class DeclinedC(unittest.TestCase):
    """At the C level: a declined launch never calls the emulation."""

    @classmethod
    def setUpClass(cls):
        if not CC:
            raise unittest.SkipTest('no C compiler')
        import gpu
        import gpu_vk
        cls._tmp = tempfile.TemporaryDirectory(prefix='ail-gpu4-decl-')
        cls.dir = Path(cls._tmp.name)
        k = g2.kernel_of(g2.comp('x * y + 1.0'), g2.FF)
        emu = gpu.emit_c(k, 'ail_gk0').replace('unsigned _f = 0;', 'unsigned _f = 0; emu_calls++;', 1)
        dev_c, info, words = gpu_vk.device_text(k, 'ail_gk0', 0, gpu.ops_expr(k))
        src = cls.dir / 'd.c'
        src.write_text(DECLINE_MAIN % dict(runtime=gpu.RUNTIME + gpu_vk.VK_RUNTIME, kernels=emu + dev_c), encoding='utf-8')
        r = subprocess.run([CC, '-O1', '-std=gnu11', '-w', str(src), '-o', str(cls.dir / 'd'), '-lm', '-ldl'],
                           capture_output=True, text=True)
        if r.returncode != 0:
            raise AssertionError(r.stderr[:3000])

    @classmethod
    def tearDownClass(cls):
        cls._tmp.cleanup()

    def go(self, **env):
        r = subprocess.run([str(self.dir / 'd')], capture_output=True, text=True, env=_env(**env), timeout=60)
        self.assertEqual(r.returncode, 0, r.stderr)
        return dict(kv.split('=', 1) for kv in r.stdout.split())

    def test_auto_declines_a_light_kernel_and_never_runs_the_emulation(self):
        got = self.go()
        self.assertEqual((got['want'], got['flag'], got['calls'], got['dev']), ('0', 'declined', '0', 'emulation'))

    def test_a_size_rule_declines_below_the_threshold(self):
        got = self.go(AIL_GPU_MIN_N='20000')
        self.assertEqual((got['want'], got['flag'], got['calls']), ('0', 'declined', '0'))

    def test_no_device_declines_instead_of_emulating(self):
        for env in (dict(AIL_GPU='force', AIL_VULKAN_LIB='/nonexistent/libvulkan.so.1'),
                    dict(AIL_GPU_MIN_N='1', AIL_VULKAN_LIB='/nonexistent/libvulkan.so.1'),
                    dict(AIL_GPU='force', AIL_GPU_DISABLE='f64')):
            got = self.go(**env)
            self.assertEqual((got['flag'], got['calls']), ('declined', '0'), env)

    def test_the_emulation_still_runs_when_asked_for(self):
        got = self.go(AIL_GPU='emu')
        self.assertEqual((got['want'], got['flag'], got['calls'], got['dev']), ('1', 'ok', '1', 'emulation'))
        self.assertEqual(float(got['r5']), 5 * 0.5 * 5 * 0.25 + 1.0)


# ---------------------------------------------------------------------------------------------------------------------
class Auto(unittest.TestCase):
    """Whole programs (the G2 program: 15 sizes x 3 kernels, special floats, 21 error kinds at 4 positions): every mode
    prints what CPython prints."""

    SCENARIOS = ('100\n', '101\n', '102\n', '103\n', '5\n0\n', '0\n64\n', '15\n4999\n', '8\n63\n', '17\n0\n')

    @classmethod
    def setUpClass(cls):
        if not CC:
            raise unittest.SkipTest('no C compiler')
        cls._tmp = tempfile.TemporaryDirectory(prefix='ail-gpu4-auto-')
        cls.dir = Path(cls._tmp.name)
        cls.b = g2.Build(cls.dir, 'g4', g2.PROGRAM)
        cls.path = cls.dir / 'g4cpy.py'
        cls.path.write_text(g2.PROGRAM.lstrip('\n'), encoding='utf-8')
        cls.cpython = {}
        cls.device = None

    @classmethod
    def tearDownClass(cls):
        cls._tmp.cleanup()

    def setUp(self):
        self.assertEqual(self.b.returncode, 0, self.b.stderr + self.b.stdout)

    def oracle(self, stdin):
        if stdin not in self.cpython:
            self.cpython[stdin] = g2.run_python(self.path, stdin)
        return self.cpython[stdin]

    def run_mode(self, stdin, **env):
        r = subprocess.run([str(self.b.exe)], input=stdin, capture_output=True, text=True, env=_env(AIL_GPU_TRACE='1', **env),
                           timeout=600)
        return r.stdout, r.returncode, r.stderr

    def have_device(self):
        if Auto.device is None:
            out, rc, err = self.run_mode('102\n', AIL_GPU='force')
            Auto.device = bool(g2.device_runs(err))
        if not Auto.device and REQUIRE_DEVICE:
            self.fail('no Vulkan device, but AIL_GPU_REQUIRE_DEVICE is set')
        return Auto.device

    def need_device(self):
        if not self.have_device():
            raise unittest.SkipTest('no Vulkan device (install mesa-vulkan-drivers for lavapipe)')

    # a model that always says yes (any device, no cold start) and one that always says no
    YES = dict(AIL_GPU_MODEL='0,0,0,1,0,0', AIL_GPU_AUTO_ANY='1')
    NO = dict(AIL_GPU_MODEL='1e12,0,0,1,1.5,0')

    def ran_on_device(self, err):
        return g2.device_runs(err)

    def no_emulation(self, err):
        self.assertFalse([l for l in g2.trace_of(err) if 'device=emulation' in l], err[:800])

    def test_the_default_prints_what_cpython_prints(self):
        for stdin in self.SCENARIOS:
            out, rc, err = self.run_mode(stdin)
            self.assertEqual((out, rc), self.oracle(stdin) if rc == 0 else (out, rc), stdin)
            out0, rc0, err0 = self.run_mode(stdin, AIL_GPU='0')
            self.assertEqual((out, rc), (out0, rc0), stdin)
            self.no_emulation(err)

    def test_a_declined_launch_runs_the_plain_loop(self):
        """Every launch the model declines runs the original loop: a trace line says so, and nothing of the emulation or
        the device runs (the trace shows a `device=` line for each of those)."""
        stdin = '100\n'
        out, rc, err = self.run_mode(stdin, **self.NO)
        self.assertEqual((out, rc), self.oracle(stdin))
        trace = g2.trace_of(err)
        self.assertEqual([l for l in trace if re.match(r'gpu: k\d+ n=\d+ device=', l)], [], err[:800])
        self.assertEqual(len([l for l in trace if 'original loop' in l]), 15 * 3, err[:800])   # n = 0 launches nothing
        self.assertEqual(len([l for l in trace if ' declined (' in l]), 15 * 3, err[:800])
        self.assertNotIn('selftest', err)                            # the device was never even opened

    def test_every_mode_prints_the_same(self):
        self.need_device()
        for stdin in self.SCENARIOS:
            want = self.run_mode(stdin, AIL_GPU='0')
            if want[1] == 0:
                self.assertEqual(want[:2], self.oracle(stdin), stdin)
            for name, env in (('default', {}), ('emu', dict(AIL_GPU='emu')), ('force', dict(AIL_GPU='force')),
                              ('auto-yes', self.YES), ('auto-no', self.NO), ('auto-explicit', dict(AIL_GPU='auto')),
                              ('min-n', dict(AIL_GPU_MIN_N='64')),
                              ('noloader', dict(AIL_GPU='force', AIL_VULKAN_LIB='/nonexistent')),
                              ('auto-noloader', dict(AIL_VULKAN_LIB='/nonexistent', **self.YES)),
                              ('auto-nofeatures', dict(AIL_GPU_DISABLE='f64,i64', **self.YES)),
                              ('auto-untrusted', dict(AIL_GPU_INJECT='flip:selftest', **self.YES)),
                              ('auto-first-launch', dict(AIL_GPU_INJECT='negzero:launch', **self.YES))):
                got = self.run_mode(stdin, **env)
                self.assertEqual(got[:2], want[:2], '%s differs for %r\n%s' % (name, stdin, got[2][:600]))
                plain = lambda e: '\n'.join(l for l in e.splitlines() if not l.startswith('gpu: '))
                self.assertEqual(plain(got[2]), plain(want[2]), '%s: stderr differs for %r' % (name, stdin))
                if name not in ('emu', 'force', 'min-n'):
                    self.no_emulation(got[2])

    def test_auto_uses_the_device_when_the_model_says_so(self):
        self.need_device()
        out, rc, err = self.run_mode('100\n', **self.YES)
        self.assertEqual((out, rc), self.oracle('100\n'))
        self.assertEqual(len(self.ran_on_device(err)), 15 * 3, err[:800])
        self.assertNotIn('original loop', err)

    def test_a_flagged_device_launch_replays_the_original_loop(self):
        self.need_device()
        for stdin in ('5\n0\n', '0\n63\n', '11\n4999\n', '14\n64\n', '15\n0\n'):
            out, rc, err = self.run_mode(stdin, **self.YES)
            want = self.run_mode(stdin, AIL_GPU='0')
            self.assertEqual((out, rc), want[:2], stdin)
            if rc == 0:
                self.assertEqual((out, rc), self.oracle(stdin), stdin)
            self.assertTrue([l for l in g2.trace_of(err) if ' replay ' in l], (stdin, err[:600]))
            self.no_emulation(err)

    def test_a_software_device_is_not_used_by_auto(self):
        """A Vulkan CPU device (lavapipe) shares the cores with the plain loop: the default never uses it."""
        self.need_device()
        out, rc, err = self.run_mode('102\n', AIL_GPU_MODEL='0,0,0,1,0,0')
        self.assertEqual((out, rc), self.oracle('102\n'))
        names = {re.match(r'gpu: k\d+ n=\d+ device=(.*)', l)[1] for l in g2.device_runs(err)}
        soft = [n for n in names if 'llvmpipe' in n or 'lavapipe' in n or 'swiftshader' in n.lower()]
        if names and not soft:
            raise unittest.SkipTest('a hardware device: %s' % sorted(names))
        self.assertFalse(names, err[:600])
        self.assertIn('software device', err)

    def test_min_n_is_still_an_override(self):
        self.need_device()
        out, rc, err = self.run_mode('100\n', AIL_GPU_MIN_N='4096')
        self.assertEqual((out, rc), self.oracle('100\n'))
        ran = {int(re.match(r'gpu: k\d+ n=(\d+) device=', l)[1]) for l in g2.device_runs(err)}
        self.assertTrue(ran and min(ran) >= 4096, sorted(ran))
        self.assertIn('is below AIL_GPU_MIN_N = 4096', err)

    def test_the_compile_note_describes_the_new_rule(self):
        notes = [l for l in self.b.stderr.splitlines() if l.startswith('note:') and 'kernel k' in l]
        self.assertTrue(notes, self.b.stderr[:800])
        self.assertTrue(all('ORIGINAL' in l and 'AIL_GPU=emu' in l for l in notes), notes[:2])


POOL_PROGRAM = r'''
def gen(n: int, seed: int) -> list[float]:
    xs = [0.0] * n
    s = seed
    for i in range(n):
        s = (s * 1103515245 + 12345) % 2147483648
        xs[i] = float(s) / 1024.0 - 1000000.0
    return xs

def geni(n: int, seed: int) -> list[int]:
    xs = [0] * n
    s = seed
    for i in range(n):
        s = (s * 1103515245 + 12345) % 2147483648
        xs[i] = s - 1073741824
    return xs

def fmap(a: list[float], b: list[float]) -> None:
    n = len(a)
    out = [0.0] * n
    # ail: gpu
    for i in range(n):
        out[i] = a[i] * b[i] - a[i] * 0.5
    t = 0.0
    for v in out:
        t = t + v
    print(n, out[0], out[n - 1], t)

def imap(a: list[int], b: list[int], c: list[int]) -> None:
    n = len(a)
    out = [0] * n
    # ail: gpu
    for i in range(n):
        out[i] = a[i] // 3 + b[i] % 7 - c[i]
    t = 0
    for v in out:
        t = t + v
    print(n, out[0], out[n - 1], t)

def main() -> None:
    for n in [50000, 4096, 70000, 64, 100003, 5000, 100003, 1, 33000, 33000]:
        fmap(gen(n, 1), gen(n, 2))
        imap(geni(n, 3), geni(n, 4), geni(n, 5))

main()
'''


class Pool(unittest.TestCase):
    """The device buffers are kept between launches (GPU.md 6.4): sizes that grow, shrink and repeat give the same output."""

    @classmethod
    def setUpClass(cls):
        if not CC:
            raise unittest.SkipTest('no C compiler')
        cls._tmp = tempfile.TemporaryDirectory(prefix='ail-gpu4-pool-')
        cls.dir = Path(cls._tmp.name)
        cls.b = g2.Build(cls.dir, 'pool', POOL_PROGRAM)
        cls.path = cls.dir / 'poolcpy.py'
        cls.path.write_text(POOL_PROGRAM.lstrip('\n'), encoding='utf-8')
        cls.want = g2.run_python(cls.path)

    @classmethod
    def tearDownClass(cls):
        cls._tmp.cleanup()

    def run_mode(self, **env):
        r = subprocess.run([str(self.b.exe)], capture_output=True, text=True, env=_env(AIL_GPU_TRACE='1', **env), timeout=600)
        return r.stdout, r.returncode, r.stderr

    def test_growing_shrinking_and_repeated_sizes(self):
        self.assertEqual(self.b.returncode, 0, self.b.stderr)
        out, rc, err = self.run_mode(AIL_GPU='force')
        self.assertEqual((out, rc), self.want, err[:800])
        if not g2.device_runs(err):
            if REQUIRE_DEVICE:
                self.fail('no Vulkan device, but AIL_GPU_REQUIRE_DEVICE is set')
            raise unittest.SkipTest('no Vulkan device (install mesa-vulkan-drivers for lavapipe)')
        self.assertEqual(len(g2.device_runs(err)), 20, err[:800])
        for env in (dict(AIL_GPU='force', AIL_GPU_KEEP_MB='0'),          # every launch releases the buffers
                    dict(AIL_GPU='force', AIL_GPU_CHECK='all'), dict(AIL_GPU='force', AIL_GPU_CHECK='0'),
                    Auto.YES, dict(AIL_GPU_MIN_N='1')):
            out, rc, err = self.run_mode(**env)
            self.assertEqual((out, rc), self.want, (env, err[:800]))
            self.assertEqual(len(g2.device_runs(err)), 20, (env, err[:800]))


class Plain(unittest.TestCase):
    def test_programs_without_the_switch_are_unchanged(self):
        if not CC:
            raise unittest.SkipTest('no C compiler')
        with tempfile.TemporaryDirectory(prefix='ail-gpu4-plain-') as d:
            b = g2.Build(d, 'plain', g2.TINY, gpu=False)
            self.assertEqual(b.returncode, 0, b.stderr)
            self.assertNotIn('GK_DECLINED', b.c)
            self.assertNotIn('gkv_decide', b.c)


if __name__ == '__main__':
    unittest.main()
