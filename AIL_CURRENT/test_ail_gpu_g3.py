"""GPU stage G3 (docs/design/GPU.md 6.3): device trust.

G2 found that lavapipe's shader compiler rewrote `0.0 - x` into `-x` although the subtraction carried NoContraction, and
that a bit test happened to contain the pattern.  Another driver may rewrite another pattern.  So since G3 no device is
trusted for a kernel until it has passed a self-test, and the first real launch of a kernel is compared with the CPU
emulation:

* the self-test runs THAT kernel's own SPIR-V over 4096 operand sets (signed zeros, inf, NaN, subnormals, the 2**-1000
  boundary, cancellation, int64 limits and overflow, out-of-range indices) and compares every clean element bit for bit
  with the emulation; a launch the emulation flags must flag on the device, and so must single flagged elements;
* the first real launch of each kernel is compared with the emulation on its first 4096 elements
  (`AIL_GPU_CHECK=all` compares every launch, `AIL_GPU_CHECK=0` skips both: for measuring only);
* a difference marks the class (binary64 or int64) untrusted for the process; every kernel of the class then takes the CPU
  path, with a trace line.  The program prints what it prints without a GPU (stdout and exit code).

The tests inject a "bad driver" through the hook `AIL_GPU_INJECT=<flip|negzero|noflag>[:selftest|:launch]` that corrupts
the device's answers (flip: last bit of every result word; negzero: +0.0 results become -0.0, the lavapipe finding;
noflag: the flag word is hidden) and check that the device is marked untrusted, that the CPU path is taken and that the
output is identical.  Device tests skip without a Vulkan device (`AIL_GPU_REQUIRE_DEVICE=1` makes that a failure).
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


def _env(**extra):
    env = g2._device_env()
    env.pop('AIL_GPU_INJECT', None)
    env.pop('AIL_GPU_CHECK', None)
    env.update(extra)
    return env


# ---------------------------------------------------------------------------------------------------------------------
class Generated(unittest.TestCase):
    """The C text of a kernel carries the self-test and the first-launch comparison; nothing changes without `--gpu`."""

    def test_wrapper_has_selftest_and_agree(self):
        import gpu
        import gpu_vk
        k = g2.kernel_of(g2.comp('x - y'), g2.FF)
        text, info, words = gpu_vk.device_text(k, 'ail_gk0', 0)
        for needle in ('ail_gk0_selftest', 'ail_gk0_agree', 'gkv_usable(GKV_T_F64 | GKV_T_I64)', 'gkv_distrust(GKV_T_F64, 0,',
                       'ail_gk0_state'):
            self.assertIn(needle, text)
        ki = g2.kernel_of(g2.comp('x + y', 'x, y', 'a, b'), g2.II)
        text, info, words = gpu_vk.device_text(ki, 'ail_gk1', 1)
        self.assertIn('gkv_usable(GKV_T_I64)', text)
        self.assertIn('gkv_distrust(GKV_T_I64, 1,', text)
        self.assertNotIn('GKV_T_F64', text)

    def test_runtime_documents_the_switches(self):
        import gpu_vk
        for word in ('AIL_GPU_CHECK', 'AIL_GPU_INJECT', 'GKV_ST_M', 'gkv_fill_f', 'gkv_fill_i'):
            self.assertIn(word, gpu_vk.VK_RUNTIME if word.startswith('gkv') or word.startswith('GKV') else gpu_vk.__doc__)

    def test_operand_sets_cover_the_edge_values(self):
        """The edge tables of the self-test are the ones of the bit tests (so a pattern the bit tests know, it knows)."""
        import gpu_vk
        rt = gpu_vk.VK_RUNTIME
        for edge in ('4.9406564584124654e-324', '9.332636185032189e-302', '-9223372036854775808.0', '1e300',
                     'INT64_MIN', 'INT64_MAX', '3037000500LL', '6148914691236517205LL', '-0.0'):
            self.assertIn(edge, rt)
        for edge in re.findall(r'EDGE_F\[\] = \{(.*?)\};', g2.HARNESS_MAIN, re.S)[0].split(','):
            edge = edge.strip()
            if edge:
                self.assertIn(edge, rt, 'the self-test lacks the bit test value %s' % edge)

    def test_programs_without_the_switch_are_unchanged(self):
        if not CC:
            raise unittest.SkipTest('no C compiler')
        with tempfile.TemporaryDirectory(prefix='ail-gpu3-plain-') as d:
            b = g2.Build(d, 'plain', g2.TINY, gpu=False)
            self.assertEqual(b.returncode, 0, b.stderr)
            self.assertNotIn('gkv_usable', b.c)
            self.assertNotIn('selftest', b.c)


# ---------------------------------------------------------------------------------------------------------------------
SELFTEST_MAIN = r'''
#include <stdio.h>
#include <stdlib.h>
#include <stdint.h>
#include <string.h>
#include <math.h>
%(runtime)s
%(kernels)s
int main(void) {
    setenv("AIL_GPU", "force", 1);
    %(calls)s
    return 0;
}
'''


def _selftest_harness(entries):
    import gpu
    import gpu_vk
    kernels, calls = [], []
    for idx, (name, src, types, scalars, args) in enumerate(entries):
        k = g2.kernel_of(src, types, scalars)
        fname = 'ail_gk%d' % idx
        kernels.append(gpu.emit_c(k, fname))
        dev_c, info, words = gpu_vk.device_text(k, fname, idx)
        kernels.append(gpu_vk.VK_RUNTIME + dev_c)
        calls.append('printf("ST %s %%d\\n", %s_selftest(%s));' % (name, fname, args))
    return SELFTEST_MAIN % dict(runtime=gpu.RUNTIME, kernels='\n'.join(kernels), calls='\n    '.join(calls))


class SelfTest(unittest.TestCase):
    """The self-test of every kernel of the G2 catalogue, run through the C entry point `ail_gk<k>_selftest`."""

    @classmethod
    def setUpClass(cls):
        if not CC:
            raise unittest.SkipTest('no C compiler')
        cls._tmp = tempfile.TemporaryDirectory(prefix='ail-gpu3-st-')
        cls.dir = Path(cls._tmp.name)
        entries = [(n, s, t, None, '') for n, s, t in g2.CATALOGUE] + [(n, s, t, None, '') for n, s, t in g2.INNER]
        entries.append(('f_scalar', 'r = [x * s + y for x, y in zip(a, b)]\n', {'a': 'f', 'b': 'f'}, {'s': 'f'}, '0.1'))
        entries.append(('i_scalar', 'r = [x * s - y for x, y in zip(a, b)]\n', {'a': 'i', 'b': 'i'}, {'s': 'i'}, '3'))
        cls.entries = entries
        src = cls.dir / 'st.c'
        src.write_text(_selftest_harness(entries), encoding='utf-8')
        cls.exe = cls.dir / 'st'
        r = subprocess.run([CC, '-O1', '-std=gnu11', '-w', str(src), '-o', str(cls.exe), '-lm', '-ldl'], capture_output=True, text=True)
        if r.returncode != 0:
            raise AssertionError(r.stderr[:3000])

    @classmethod
    def tearDownClass(cls):
        cls._tmp.cleanup()

    def results(self, **env):
        r = subprocess.run([str(self.exe)], capture_output=True, text=True, env=_env(**env), timeout=900)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        got = {m[1]: int(m[2]) for m in (re.match(r'ST (\S+) (-?\d+)', l) for l in r.stdout.splitlines()) if m}
        self.assertEqual(sorted(got), sorted(e[0] for e in self.entries), r.stdout)
        if all(v == 0 for v in got.values()):
            if REQUIRE_DEVICE:
                self.fail('no Vulkan device, but AIL_GPU_REQUIRE_DEVICE is set')
            raise unittest.SkipTest('no Vulkan device (install mesa-vulkan-drivers for lavapipe)')
        return got, r.stderr

    def test_the_device_passes_every_kernel(self):
        got, err = self.results(AIL_GPU_TRACE='1')
        self.assertEqual({n: v for n, v in got.items() if v != 1}, {}, err)
        self.assertEqual(len(re.findall(r'selftest ok', err)), len(self.entries), err)

    def test_a_flipped_bit_is_found_in_every_kernel(self):
        got, err = self.results(AIL_GPU_INJECT='flip:selftest')
        self.assertEqual({n: v for n, v in got.items() if v != -1}, {}, got)

    def test_a_hidden_flag_is_found(self):
        got, err = self.results(AIL_GPU_INJECT='noflag:selftest')
        for name in ('f_add', 'f_mul', 'f_fma3', 'i_add', 'i_mul', 'i_fdiv', 'v_int', 'r_gather'):
            self.assertEqual(got[name], -1, (name, got))

    def test_the_lavapipe_pattern_is_found(self):
        """+0.0 results turned into -0.0 (what lavapipe did to `0.0 - x`): found as soon as a kernel produces +0.0."""
        got, err = self.results(AIL_GPU_INJECT='negzero:selftest', AIL_GPU_TRACE='1')
        for name in ('f_sub', 'f_add', 'f_neg0', 'f_negzero', 'f_chain', 'f_two_mul'):
            self.assertEqual(got[name], -1, (name, got))
        self.assertIn('differs from the CPU emulation: result bits differ', err)
        self.assertIn('untrusted for binary64 kernels', err)


class RealBug(unittest.TestCase):
    """The G2 finding itself: the emitter without its workaround (`zero_sign`, the integer select that fixes the sign of an
    exact zero) hands the driver a plain `0.0 - x`; lavapipe rewrites that into `-x`.  The self-test must see it.  If the
    driver under test does not have the bug the mutant passes and the test says so (nothing to prove on that driver)."""

    def test_the_self_test_finds_the_unworked_around_zero_sign(self):
        if not CC:
            raise unittest.SkipTest('no C compiler')
        from unittest import mock
        import gpu_spirv
        entries = [(n, s, t, None, '') for n, s, t in g2.CATALOGUE if n in ('f_neg0', 'f_sub', 'f_add', 'f_mul', 'f_negzero')]
        with tempfile.TemporaryDirectory(prefix='ail-gpu3-mut-') as d:
            res = {}
            for label, patched in (('control', False), ('mutant', True)):
                if patched:
                    with mock.patch.object(gpu_spirv.Gen, 'zero_sign', lambda self, r, sign_bits: r):
                        text = _selftest_harness(entries)
                else:
                    text = _selftest_harness(entries)
                src = Path(d) / (label + '.c')
                src.write_text(text, encoding='utf-8')
                exe = Path(d) / label
                r = subprocess.run([CC, '-O1', '-std=gnu11', '-w', str(src), '-o', str(exe), '-lm', '-ldl'], capture_output=True, text=True)
                self.assertEqual(r.returncode, 0, r.stderr[:2000])
                r = subprocess.run([str(exe)], capture_output=True, text=True, env=_env(AIL_GPU_TRACE='1'), timeout=600)
                res[label] = ({m[1]: int(m[2]) for m in (re.match(r'ST (\S+) (-?\d+)', l) for l in r.stdout.splitlines()) if m}, r.stderr)
            control, _ = res['control']
            if all(v == 0 for v in control.values()):
                if REQUIRE_DEVICE:
                    self.fail('no Vulkan device, but AIL_GPU_REQUIRE_DEVICE is set')
                raise unittest.SkipTest('no Vulkan device')
            self.assertEqual(set(control.values()), {1}, control)
            mutant, err = res['mutant']
            if set(mutant.values()) == {1}:
                raise unittest.SkipTest('this driver does not rewrite 0.0 - x: the mutant is as good as the real emitter')
            self.assertIn(-1, mutant.values(), mutant)
            self.assertIn('differs from the CPU emulation', err)


# ---------------------------------------------------------------------------------------------------------------------
PROGRAM = r'''
def gen(n: int, seed: int) -> list[float]:
    xs = [0.0] * n
    s = seed
    for i in range(n):
        s = (s * 1103515245 + 12345) % 2147483648
        xs[i] = float(s % 2001 - 1000) * 0.25
    return xs

def geni(n: int, seed: int) -> list[int]:
    xs = [0] * n
    s = seed
    for i in range(n):
        s = (s * 1103515245 + 12345) % 2147483648
        xs[i] = s % 1000 + 1
    return xs

def sub(a: list[float], b: list[float]) -> None:
    n = len(a)
    out = [0.0] * n
    # ail: gpu
    for i in range(n):
        out[i] = a[i] - b[i]
    print(out[0], out[1], out[2], sum(out), len(out))
    print(out)

def mul(a: list[float], b: list[float]) -> None:
    n = len(a)
    out = [0.0] * n
    # ail: gpu
    for i in range(n):
        out[i] = a[i] * b[i] + 1.5
    print(out[0], out[1], sum(out), len(out))

def addi(a: list[int], b: list[int]) -> None:
    n = len(a)
    out = [0] * n
    # ail: gpu
    for i in range(n):
        out[i] = a[i] * 3 + b[i]
    print(out[0], out[1], sum(out), len(out))

def main() -> None:
    a = gen(5000, 1)
    sub(a, a)
    sub(a, gen(5000, 2))
    mul(a, gen(5000, 3))
    addi(geni(5000, 4), geni(5000, 5))
    addi(geni(5000, 6), geni(5000, 7))

main()
'''


class Programs(unittest.TestCase):
    """Whole programs under a simulated bad driver: untrusted device, CPU path taken, identical output."""

    @classmethod
    def setUpClass(cls):
        if not CC:
            raise unittest.SkipTest('no C compiler')
        cls._tmp = tempfile.TemporaryDirectory(prefix='ail-gpu3-prog-')
        cls.build = g2.Build(cls._tmp.name, 'trust', PROGRAM)
        if cls.build.returncode != 0:
            raise AssertionError(cls.build.stderr[:3000])
        cls.want = g2.run_python(cls.build.src)

    @classmethod
    def tearDownClass(cls):
        cls._tmp.cleanup()

    def run_with(self, **env):
        out, rc, err = self.build.run('', AIL_GPU='force', AIL_GPU_TRACE='1', **{k: v for k, v in env.items()})
        return out, rc, err

    def device_launches(self, err):
        return g2.device_runs(err)

    def need_device(self):
        out, rc, err = self.run_with()
        if not self.device_launches(err):
            if REQUIRE_DEVICE:
                self.fail('no Vulkan device, but AIL_GPU_REQUIRE_DEVICE is set:\n' + err)
            raise unittest.SkipTest('no Vulkan device (install mesa-vulkan-drivers for lavapipe)')
        return out, rc, err

    def test_a_good_device_is_tested_once_per_kernel_and_trusted(self):
        out, rc, err = self.need_device()
        self.assertEqual((out, rc), self.want, err)
        self.assertEqual(len(re.findall(r'selftest ok', err)), 3, err)          # sub, mul, addi: one self-test each
        self.assertNotIn('untrusted', err)
        # every launch of every kernel ran on the device: 5 launches
        self.assertEqual(len(self.device_launches(err)), 5, err)

    def test_the_selftest_can_be_skipped_for_measuring(self):
        self.need_device()
        out, rc, err = self.run_with(AIL_GPU_CHECK='0')
        self.assertEqual((out, rc), self.want, err)
        self.assertNotIn('selftest', err)
        self.assertEqual(len(self.device_launches(err)), 5, err)

    def test_a_bad_device_found_by_the_selftest(self):
        self.need_device()
        for inject in ('negzero:selftest', 'flip:selftest', 'noflag:selftest'):
            out, rc, err = self.run_with(AIL_GPU_INJECT=inject)
            self.assertEqual((out, rc), self.want, (inject, err))
            self.assertIn('differs from the CPU emulation', err, inject)
            self.assertIn('untrusted for binary64 kernels', err, inject)
            # the hook corrupts every kernel's answers, so no kernel runs on the device at all
            self.assertEqual(self.device_launches(err), [], (inject, err))
            self.assertIn('gpu: k0 original loop', err)          # GPU.md 6.4: the declined launch runs the plain loop, not the emulation
            self.assertNotIn('device=emulation', err)

    def test_a_bad_device_found_by_the_first_launch(self):
        """The self-test passes (the injection aims at launches), the comparison of the first real launch finds it."""
        self.need_device()
        for inject in ('negzero:launch', 'flip:launch'):
            out, rc, err = self.run_with(AIL_GPU_INJECT=inject)
            self.assertEqual((out, rc), self.want, (inject, err))
            self.assertIn('selftest ok', err, inject)
            self.assertIn('differs from the CPU emulation', err, inject)
            self.assertIn('untrusted for binary64 kernels', err, inject)
            # sub(a, a) is the first launch: its device answer is thrown away and the original loop runs (GPU.md 6.4)
            self.assertIn('gpu: k0 original loop', err, (inject, err))
            self.assertFalse([l for l in g2.trace_of(err) if l.startswith('gpu: k0 n=')], (inject, err))
            # the second float kernel never touches the device either
            self.assertIn('gpu: k1 original loop', err, (inject, err))
            self.assertFalse([l for l in g2.trace_of(err) if l.startswith('gpu: k1 n=')], (inject, err))

    def test_a_hidden_flag_is_found_by_the_first_launch(self):
        self.need_device()
        out, rc, err = self.run_with(AIL_GPU_INJECT='noflag:launch')
        self.assertEqual((out, rc), self.want, err)
        # the programs of this module raise no flag, so a hidden flag changes nothing; it must at least not break anything
        self.assertNotIn('Traceback', err)

    def test_every_launch_can_be_compared(self):
        """AIL_GPU_CHECK=all compares each launch, not only the first: a driver that goes bad later is found."""
        self.need_device()
        out, rc, err = self.run_with(AIL_GPU_CHECK='all')
        self.assertEqual((out, rc), self.want, err)
        self.assertNotIn('untrusted', err)

    def test_the_cpu_path_without_a_device_prints_the_same(self):
        for env in (dict(AIL_GPU='emu'), dict(AIL_GPU='0'), dict(AIL_VULKAN_LIB='/nonexistent'),
                    dict(AIL_VULKAN_LIB='/nonexistent', AIL_GPU_INJECT='flip')):
            out, rc, err = self.build.run('', AIL_GPU_TRACE='1', **env)
            self.assertEqual((out, rc), self.want, (env, err))


if __name__ == '__main__':
    unittest.main()
