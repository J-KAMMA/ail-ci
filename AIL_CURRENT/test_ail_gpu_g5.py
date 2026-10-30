"""GPU stage G5 (docs/design/GPU.md 6.5): typed arrays (`ail_array`, TYPED_ARRAY.md T2) on the device.

What goes to the device, in a `compile --gpu` build only (without the switch the lowering of ailarray.py is T2's, byte for byte):

* f64 element-wise `+ - *` and unary minus, FUSED: `c = a * b + a` is one generated function with one loop (one kernel), not
  three passes; a scalar operand is a kernel parameter; the operands of a chain are plain names (so that evaluating them first
  cannot change which error comes first) and the shape errors are raised in the order of the unfused code;
* `ta.sum` / `ta.dot` of f64: the whole blocks of 1024 elements are one invocation each (16 lanes of 64 adds, then the 8-4-2-1
  tree), the short last block and the tree over the blocks run on the CPU: the order of TYPED_ARRAY.md 3.5 on every device;
* int32 `+ - *` between arrays and with a scalar, one kernel per operation; the int32 range is checked in the kernel (IR node
  `c32`), an out-of-range element sets the overflow flag and the CPU replay raises the OverflowError of T2, index and all.

Every mode (AIL_GPU=0, emu, force, auto declined, auto on the device, no loader, a device without features, an untrusted
device) must print what CPython prints running the T1 reference `ail_array.py` on the same program.  Device tests skip without
a Vulkan device; the `gpu` CI job installs lavapipe and sets AIL_GPU_REQUIRE_DEVICE=1.
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
for p in (str(ROOT), str(PKG)):
    if p not in sys.path:
        sys.path.insert(0, p)

import test_ail_gpu_g2 as g2                                    # noqa: E402  (helpers only)
import test_ail_gpu_g3 as g3                                    # noqa: E402

CASES = ROOT / 'array_g5_cases'
CC = g2.CC
REQUIRE_DEVICE = g2.REQUIRE_DEVICE
_env = g3._env


def lowered(source, gpu_build):
    """The text ailarray.rewrite_text makes, with or without the `--gpu` switch."""
    import ailarray
    old = os.environ.get('AIL_GPU_BUILD')
    try:
        if gpu_build:
            os.environ['AIL_GPU_BUILD'] = '1'
        else:
            os.environ.pop('AIL_GPU_BUILD', None)
        notes = []
        out = ailarray.rewrite_text(source, notes)
        assert not notes, notes
        return out
    finally:
        if old is None:
            os.environ.pop('AIL_GPU_BUILD', None)
        else:
            os.environ['AIL_GPU_BUILD'] = old


HEAD = 'import ail_array as ta\n\n\n'


class Lowering(unittest.TestCase):
    """The text level: what is fused, what is not, and that nothing changes without the switch."""

    def test_without_the_switch_nothing_is_added(self):
        src = HEAD + 'def f(a: ta.Array[ta.f64], b: ta.Array[ta.f64]):\n    return ta.sum(a * b + a)\n'
        text = lowered(src, False)
        for needle in ('_ailg_', '_ail_taf_fu', '_ail_taf_gsum', '_ail_ta_c32', '_ail_tai_ia'):
            self.assertNotIn(needle, text)
        self.assertIn('_ail_taf_bin', text)

    def test_a_chain_is_one_function_one_loop(self):
        src = HEAD + ('def f(a: ta.Array[ta.f64], b: ta.Array[ta.f64], c: ta.Array[ta.f64], s: float):\n'
                      '    return (a * b + a) - c * 0.5 + s * a\n')
        text = lowered(src, True)
        self.assertEqual(text.count('for _ailg_map in range(n)'), 1)
        self.assertEqual(len(re.findall(r'def _ail_taf_fu\d+\(', text)), 1)
        self.assertNotIn('_ail_taf_bin', text)
        loop = re.search(r'o = \[_ail_ta_cn\((.*), inf\) for _ailg_map in range\(n\)\]', text).group(1)
        self.assertIn('x0[_ailg_map]', loop)
        self.assertEqual(loop.count('*'), 3)
        self.assertEqual(loop.count('+') + loop.count('-'), 3)

    def test_the_same_shape_shares_a_function(self):
        src = HEAD + ('def f(a: ta.Array[ta.f64], b: ta.Array[ta.f64], c: ta.Array[ta.f64]):\n'
                      '    return (a * b + a, b * c + b, ta.sum(a), ta.sum(b), ta.dot(a, b))\n')
        text = lowered(src, True)
        self.assertEqual(len(re.findall(r'def _ail_taf_fu\d+\(', text)), 1)
        self.assertEqual(len(re.findall(r'def _ail_taf_gk_sum\(', text)), 1)
        self.assertEqual(len(re.findall(r'def _ail_taf_gk_dot\(', text)), 0)    # ta.dot's CPU loop is slower than T2's: opt-in
        os.environ['AIL_GPU_ARRAY_SLOW'] = '1'
        try:
            text = lowered(src, True)
        finally:
            os.environ.pop('AIL_GPU_ARRAY_SLOW', None)
        self.assertEqual(len(re.findall(r'def _ail_taf_gk_dot\(', text)), 1)

    def test_division_is_not_fused_and_what_is_around_it_still_is(self):
        src = HEAD + ('def f(a: ta.Array[ta.f64], b: ta.Array[ta.f64], c: ta.Array[ta.f64]):\n'
                      '    return a / b + c * c\n')
        text = lowered(src, True)
        self.assertIn('_ail_taf_bin(', text)                       # the division stays T2's
        self.assertEqual(text.count('for _ailg_map in range(n)'), 2)    # c * c and the addition, one operation each

    def test_a_call_among_the_operands_is_not_reordered(self):
        src = HEAD + ('def g(a: ta.Array[ta.f64]) -> ta.Array[ta.f64]:\n    return a\n\n\n'
                      'def f(a: ta.Array[ta.f64], b: ta.Array[ta.f64]):\n    return g(a) * b + g(b) * a\n')
        text = lowered(src, True)
        # the two calls are operands of single operations: evaluated where they stood, in order
        self.assertNotIn('x1[_ailg_map] * x0', text)
        self.assertEqual(text.count('for _ailg_map in range(n)'), 2)        # the two products share one kernel, the sum has its own

    def test_int32_is_opt_in_and_has_one_kernel_per_operation(self):
        src = HEAD + ('def f(a: ta.Array[ta.int32], b: ta.Array[ta.int32]):\n'
                      '    return (a + b * a, a - 3, 3 - a, a * 2, a // b)\n')
        self.assertNotIn('_ail_ta_c32', lowered(src, True))            # not without AIL_GPU_ARRAY_SLOW
        os.environ['AIL_GPU_ARRAY_SLOW'] = '1'
        try:
            text = lowered(src, True)
        finally:
            os.environ.pop('AIL_GPU_ARRAY_SLOW', None)
        self.assertEqual(len(re.findall(r'for _ailg_map in range\(n\)', text)), 5)     # +, *, -s, s-, *s
        self.assertIn('_ail_tai_bin(', text)                          # // is T2's

    def test_the_prelude_kernels_are_ordinary_python(self):
        """The generated text and the new prelude functions run under CPython and equal the reference (white box)."""
        os.environ['AIL_GPU_ARRAY_SLOW'] = '1'
        self.addCleanup(os.environ.pop, 'AIL_GPU_ARRAY_SLOW', None)
        for name in ('fused', 'int32', 'sumdot'):
            with self.subTest(case=name), tempfile.TemporaryDirectory() as tmp:
                tmp = Path(tmp)
                source = (CASES / (name + '.py')).read_text(encoding='utf-8')
                (tmp / 'ref').mkdir()
                shutil.copy(ROOT / 'ail_array.py', tmp / 'ref' / 'ail_array.py')
                (tmp / 'ref' / 'prog.py').write_text(source, encoding='utf-8')
                (tmp / 'low.py').write_text(lowered(source, True), encoding='utf-8')
                env = dict(os.environ, PYTHONDONTWRITEBYTECODE='1')
                env.pop('PYTHONPATH', None)
                ref = subprocess.run([sys.executable, '-B', 'prog.py'], cwd=tmp / 'ref', capture_output=True, text=True, env=env, timeout=900)
                got = subprocess.run([sys.executable, '-B', 'low.py'], cwd=tmp, capture_output=True, text=True, env=env, timeout=900)
                self.assertEqual((got.returncode, got.stdout), (ref.returncode, ref.stdout), got.stderr[-800:])


class Kernels(unittest.TestCase):
    """The new IR node and the shape of the new kernels."""

    def test_c32_in_spirv_and_in_the_emulation(self):
        import gpu
        import gpu_spirv
        k = g2.kernel_of('o = [0] * 8\nfor i in range(8):\n    o[i] = _ail_ta_c32(a[i] + b[i], 0, i)\n', g2.II)
        words, info = gpu_spirv.compile_kernel(k)
        self.assertFalse(info['need_f64'])
        c = gpu.emit_c(k, 'k0')
        self.assertIn('gk_c32(', c)
        self.assertIn('2147483647LL', gpu.RUNTIME)

    def test_sum_kernel_is_a_range_kernel_over_blocks(self):
        import ailarray
        import gpu
        os.environ['AIL_GPU_BUILD'] = '1'
        try:
            text = lowered(HEAD + 'def f(a: ta.Array[ta.f64]):\n    return ta.sum(a)\n', True)
        finally:
            os.environ.pop('AIL_GPU_BUILD', None)
        tree = ast.parse(text)
        fn = [n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == '_ail_taf_gk_sum'][0]
        loop = [n for n in ast.walk(fn) if isinstance(n, ast.For) and gpu.internal_kind(n) == 'sum'][0]
        site = gpu._classify(loop, {})
        site['k'] = 0
        site['internal'] = 'sum'
        k = gpu.Builder(site, {}, lambda what, name, node: 'f' if what == 'list' else 'i').build_for()
        self.assertEqual(k.kind, 'sum')
        self.assertEqual(set(k.lists), {'d'})
        ops = gpu.ops_expr(k)
        self.assertIn('gkv_trip', ops)


# ---------------------------------------------------------------------------------------------------------------------
class Programs(unittest.TestCase):
    """The three case programs (array_g5_cases/): sums and dots at every lane and block boundary with inf / NaN / -0.0 / 1e308 /
    a subnormal planted at the boundaries, fused chains of every shape at the sizes that matter, int32 operations with overflow
    at chosen positions.  Each prints what CPython prints with the reference, in every mode."""

    NAMES = ('sumdot', 'fused', 'int32')
    YES = dict(AIL_GPU_MODEL='0,0,0,1,0,0', AIL_GPU_AUTO_ANY='1')
    NO = dict(AIL_GPU_MODEL='1e12,0,0,1,1.5,0')

    @classmethod
    def setUpClass(cls):
        if not CC:
            raise unittest.SkipTest('no C compiler')
        cls._tmp = tempfile.TemporaryDirectory(prefix='ail-gpu5-')
        cls.dir = Path(cls._tmp.name)
        cls.builds, cls.want = {}, {}
        (cls.dir / 'ref').mkdir()
        shutil.copy(ROOT / 'ail_array.py', cls.dir / 'ref' / 'ail_array.py')
        for name in cls.NAMES:
            text = (CASES / (name + '.py')).read_text(encoding='utf-8')
            cls.builds[name] = g2.Build(cls.dir, name, text, env={'AIL_NO_GENERAL': '1', 'AIL_GPU_ARRAY_SLOW': '1'})
            (cls.dir / 'ref' / (name + '.py')).write_text(text, encoding='utf-8')
            env = dict(os.environ, PYTHONDONTWRITEBYTECODE='1')
            env.pop('PYTHONPATH', None)
            r = subprocess.run([sys.executable, '-B', name + '.py'], cwd=cls.dir / 'ref', capture_output=True, text=True, env=env, timeout=900)
            cls.want[name] = (r.stdout, r.returncode)
        cls.device = None

    @classmethod
    def tearDownClass(cls):
        cls._tmp.cleanup()

    def run_mode(self, name, **env):
        b = self.builds[name]
        self.assertEqual(b.returncode, 0, b.stderr[-1500:])
        r = subprocess.run([str(b.exe)], capture_output=True, text=True, env=_env(AIL_GPU_TRACE='1', **env), timeout=900)
        return r.stdout, r.returncode, r.stderr

    def need_device(self):
        if Programs.device is None:
            Programs.device = bool(g2.device_runs(self.run_mode('int32', AIL_GPU='force')[2]))
        if not Programs.device:
            if REQUIRE_DEVICE:
                self.fail('no Vulkan device, but AIL_GPU_REQUIRE_DEVICE is set')
            raise unittest.SkipTest('no Vulkan device (install mesa-vulkan-drivers for lavapipe)')

    def test_the_programs_stay_on_the_typed_path_and_have_kernels(self):
        for name in self.NAMES:
            b = self.builds[name]
            self.assertEqual(b.returncode, 0, b.stderr[-1500:])
            self.assertGreaterEqual(b.c.count('gpu loop k'), 2, name)
            self.assertIn('ail_array: kernel k', b.stderr)

    def test_off_and_the_default_print_what_cpython_prints(self):
        for name in self.NAMES:
            for env in (dict(AIL_GPU='0'), {}, self.NO):
                out, rc, err = self.run_mode(name, **env)
                self.assertEqual((out, rc), self.want[name], (name, env, err[-400:]))
                self.assertFalse([l for l in g2.trace_of(err) if 'device=' in l], (name, env))

    def test_every_other_mode_prints_the_same(self):
        self.need_device()
        for name in self.NAMES:
            for label, env in (('emu', dict(AIL_GPU='emu')), ('force', dict(AIL_GPU='force')), ('auto-device', self.YES),
                               ('noloader', dict(AIL_GPU='force', AIL_VULKAN_LIB='/nonexistent')),
                               ('auto-noloader', dict(AIL_VULKAN_LIB='/nonexistent', **self.YES)),
                               ('nofeatures', dict(AIL_GPU='force', AIL_GPU_DISABLE='f64,i64')),
                               ('untrusted-selftest', dict(AIL_GPU='force', AIL_GPU_INJECT='flip:selftest')),
                               ('untrusted-launch', dict(AIL_GPU='force', AIL_GPU_INJECT='flip:launch'))):
                out, rc, err = self.run_mode(name, **env)
                self.assertEqual((out, rc), self.want[name], '%s %s\n%s' % (name, label, err[-600:]))

    def test_force_and_auto_really_use_the_device(self):
        self.need_device()
        for name in self.NAMES:
            for env in (dict(AIL_GPU='force'), self.YES):
                err = self.run_mode(name, **env)[2]
                self.assertGreater(len(g2.device_runs(err)), 10, (name, env))
                self.assertFalse([l for l in g2.trace_of(err) if 'device=emulation' in l])

    def test_the_selftest_of_every_new_kernel_passes(self):
        """G3 coverage of the new ops: each kernel of each program passes its own self-test (the block kernels on blocks of 1024
        with rounding, absorption, signed zeros, overflow to inf, cancellation and blocks that must flag; the int32 kernels on
        the int32 boundary pairs)."""
        self.need_device()
        for name in self.NAMES:
            err = self.run_mode(name, AIL_GPU='force')[2]
            ran = {m[1] for m in (re.match(r'gpu: (k\d+) n=\d+ device=(?!emulation)', l) for l in g2.trace_of(err)) if m}
            ok = {m[1] for m in (re.match(r'gpu: (k\d+) selftest ok', l) for l in g2.trace_of(err)) if m}
            self.assertTrue(ran, name)
            self.assertEqual(ran - ok, set(), (name, err[-800:]))
            self.assertNotIn('differs from the CPU emulation', err)

    def test_a_bad_driver_is_found_for_the_new_kernels(self):
        self.need_device()
        for name in self.NAMES:
            for inject in ('flip:selftest', 'negzero:selftest', 'noflag:selftest'):
                out, rc, err = self.run_mode(name, AIL_GPU='force', AIL_GPU_INJECT=inject)
                self.assertEqual((out, rc), self.want[name], (name, inject))
                self.assertIn('differs from the CPU emulation', err, (name, inject))
                self.assertEqual(g2.device_runs(err), [], (name, inject))

    def test_auto_declines_the_light_kernels_and_the_sums(self):
        """The model of GPU.md 6.4 with the ops counts of the new kernels: a three-operation chain, int32 additions and
        sums never pay for their copy; they run the original loop (the T2 loop, fused)."""
        for name in self.NAMES:
            out, rc, err = self.run_mode(name)
            self.assertEqual((out, rc), self.want[name])
            self.assertIn('original loop', err)


class Long(unittest.TestCase):
    """A long fused chain (the one place the model sends to a device): Horner's rule of degree 40 on 20000 elements."""

    SRC = '''
import ail_array as ta


def f(x: ta.Array[ta.f64]) -> ta.Array[ta.f64]:
    return @@


def main() -> None:
    n = 20000
    x = ta.zeros(n, ta.f64)
    for k in range(n):
        x[k] = (k % 2001 - 1000) / 1000.0
    x[7] = -0.0
    y = f(x)
    print(ta.sum(y), y[0], y[7], y[n - 1], y[12345])


main()
'''

    @classmethod
    def horner(cls, d):
        e = '0.5'
        for i in range(d):
            e = '(%s * x + %r)' % (e, 0.25 + 0.015625 * i)
        return e

    @classmethod
    def setUpClass(cls):
        if not CC:
            raise unittest.SkipTest('no C compiler')
        cls._tmp = tempfile.TemporaryDirectory(prefix='ail-gpu5-long-')
        cls.dir = Path(cls._tmp.name)
        text = cls.SRC.replace('@@', cls.horner(40))
        cls.b = g2.Build(cls.dir, 'horner', text, env={'AIL_NO_GENERAL': '1'})
        (cls.dir / 'ref').mkdir()
        shutil.copy(ROOT / 'ail_array.py', cls.dir / 'ref' / 'ail_array.py')
        (cls.dir / 'ref' / 'horner.py').write_text(text, encoding='utf-8')
        env = dict(os.environ, PYTHONDONTWRITEBYTECODE='1')
        env.pop('PYTHONPATH', None)
        r = subprocess.run([sys.executable, '-B', 'horner.py'], cwd=cls.dir / 'ref', capture_output=True, text=True, env=env, timeout=600)
        cls.want = (r.stdout, r.returncode)

    @classmethod
    def tearDownClass(cls):
        cls._tmp.cleanup()

    def run_mode(self, **env):
        self.assertEqual(self.b.returncode, 0, self.b.stderr[-1500:])
        r = subprocess.run([str(self.b.exe)], capture_output=True, text=True, env=_env(AIL_GPU_TRACE='1', **env), timeout=600)
        return r.stdout, r.returncode, r.stderr

    def test_the_chain_is_one_kernel_with_many_operations(self):
        self.assertEqual(self.b.c.count('gpu loop k'), 2)      # the chain, and the blocks of ta.sum
        self.assertIn('for (int64_t', self.b.c)

    def test_all_modes_agree(self):
        for env in (dict(AIL_GPU='0'), dict(AIL_GPU='emu'), dict(AIL_GPU='force'), Programs.YES, Programs.NO, {}):
            out, rc, err = self.run_mode(**env)
            if env.get('AIL_GPU') in ('force',) or env is Programs.YES:
                if not g2.device_runs(err):
                    if REQUIRE_DEVICE:
                        self.fail('no device')
                    raise unittest.SkipTest('no Vulkan device')
            self.assertEqual((out, rc), self.want, (env, err[-500:]))

    def test_auto_sends_the_long_chain_to_the_device_and_not_the_short_one(self):
        out, rc, err = self.run_mode(AIL_GPU_MODEL='0,0.17,0.06,0.2,1.5,0', AIL_GPU_AUTO_ANY='1')
        if not g2.device_runs(err):
            if REQUIRE_DEVICE:
                self.fail('no device')
            raise unittest.SkipTest('no Vulkan device')
        self.assertEqual((out, rc), self.want)
        launches = [l for l in g2.device_runs(err)]
        self.assertGreaterEqual(len(launches), 1)
        declined = [l for l in g2.trace_of(err) if ' declined (' in l]
        self.assertTrue(declined, err[-600:])          # sum(y) and y[...] are light: declined


if __name__ == '__main__':
    unittest.main()
