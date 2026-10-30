"""Fusion of f64 `ail_array` expressions in every build (docs/design/TYPED_ARRAY.md 5.2a, built on the G5 fusion of GPU.md 6.5).

`a * b + a` is one generated function with one loop, not three passes with an array for each result; the same for `/`, `abs`,
`minimum`, `maximum`, `clip`, the in-place forms `a += b * c`, and `ta.sum(expr)` / `ta.dot(x, expr)` (the expression is computed one
block of 1024 elements at a time into a scratch array that is added in the fixed order of design 3.5).  The rule of the project is zero
silent differences: every result must have the bits of the T1 reference `ail_array.py` running under CPython, which makes a NaN canonical
after every operation, raises the shape error of the FIRST failing check, and rounds every operation separately.

* Lowering: the text the pass makes (what is fused, what is not, the order of the checks, one canonicalisation, shared functions).
* Bits: the lowered text run by CPython equals the reference on the case programs (`array_fuse_cases/`: chains, in-place, sums and dots with
  specials planted at the lane and block boundaries, evaluation order of calls among the operands, and `grid.py`, every operand triple of 14
  special values through 48 patterns of two operations).
* Programs: the same programs built by the compiler (typed path), default build and AIL_UNIFIED_FORCE=1, print what CPython prints.
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

CASES = ROOT / 'array_fuse_cases'
CLI = ROOT / 'ail_chatgpt.py'
CC = shutil.which('cc') or shutil.which('gcc')
NAMES = ('chains', 'inplace', 'reduce', 'order', 'grid')
HEAD = 'import ail_array as ta\n\n\n'
F = 'a: ta.Array[ta.f64], b: ta.Array[ta.f64], c: ta.Array[ta.f64]'


def lowered(source, gpu_build=False):
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


def functions(text, prefix):
    """{name: source} of the generated functions whose name starts with `prefix`."""
    tree = ast.parse(text)
    return {n.name: ast.get_source_segment(text, n) for n in tree.body if isinstance(n, ast.FunctionDef) and n.name.startswith(prefix)}


def clean_env():
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE='1')
    for key in ('PYTHONPATH', 'AIL_GPU_BUILD', 'AIL_UNIFIED_FORCE', 'AIL_GPU', 'AIL_GPU_ARRAY_SLOW'):
        env.pop(key, None)
    return env


class Lowering(unittest.TestCase):
    """The text level."""

    def test_a_chain_is_one_function_with_one_loop(self):
        text = lowered(HEAD + 'def f(%s, s: float):\n    return (a * b + a) - c * 0.5 + s * a\n' % F)
        self.assertNotIn('_ail_taf_bin', text)
        self.assertNotIn('_ailg_', text)
        fk = functions(text, '_ail_taf_fk')
        self.assertEqual(len(fk), 1)
        body = list(fk.values())[0]
        self.assertEqual(body.count('for k in range(n)'), 1)
        self.assertEqual(len(re.findall(r'^\s+t\d+ = \S+ \* \S+$', body, re.M)), 3, body)
        self.assertEqual(len(functions(text, '_ail_taf_fu')), 1)

    def test_a_single_operation_is_a_loop_of_its_own(self):
        """T2's `_ail_taf_aa` loops over objects and costs about twice the instructions of the list loop of a generated kernel."""
        text = lowered(HEAD + 'def f(%s):\n    return (a + b, -a, abs(a), a / b, ta.minimum(a, b), a * 2.0, 3.0 - a)\n' % F)
        self.assertEqual(len(functions(text, '_ail_taf_fu')), 7)
        self.assertNotIn('_ail_taf_bin', text)
        self.assertNotIn('_ail_taf_aa', text)

    def test_an_operand_that_is_a_call_keeps_its_place(self):
        text = lowered(HEAD + 'def g(a: ta.Array[ta.f64]) -> ta.Array[ta.f64]:\n    return a\n\n\n'
                       'def f(%s):\n    return g(a) + b\n' % F)
        self.assertIn('_ail_taf_fu0(g(a), b)', text)

    def test_the_nan_is_made_canonical_once_at_the_end(self):
        text = lowered(HEAD + 'def f(%s):\n    return ((a * b + c) * a - b) * c + a\n' % F)
        body = list(functions(text, '_ail_taf_fk').values())[0]
        self.assertEqual(len(re.findall(r'if (t\d+) != \1:', body)), 1, body)
        self.assertEqual(body.count('= nan'), 1, body)
        self.assertTrue(re.search(r'if (t\d+) != \1:\n\s+\1 = nan\n\s+o\[k\] = \1', body), body)

    def test_minimum_maximum_and_clip_need_no_canonicalisation_at_the_end(self):
        text = lowered(HEAD + 'def f(%s, s: float):\n    return ta.clip(a * b, -s, s)\n' % F)
        body = list(functions(text, '_ail_taf_fk').values())[0]
        self.assertEqual(len(re.findall(r'if (t\d+) != \1:', body)), 0, body)
        self.assertIn('_ail_ta_fless', body)

    def test_division_is_ieee_like_t2(self):
        text = lowered(HEAD + 'def f(%s):\n    return a * b / c + a\n' % F)
        body = list(functions(text, '_ail_taf_fk').values())[0]
        self.assertIn('== 0.0', body)
        self.assertIn('_ail_ta_fdiv0', body)

    def test_the_checks_come_in_the_order_of_the_unfused_code(self):
        text = lowered(HEAD + 'def f(%s):\n    return a * a + b * c\n' % F)
        fu = list(functions(text, '_ail_taf_fu').values())[0]
        lines = [l.strip() for l in fu.splitlines()]
        # a * a (nothing), b * c (b against c), then a * a + b * c (a against b)
        want = ['if len(a2.d) != len(a1.d):', '_ail_ta_shapes(len(a1.d), len(a2.d))',
                'if len(a1.d) != len(a0.d):', '_ail_ta_shapes(len(a0.d), len(a1.d))']
        got = [l for l in lines if l.startswith('if len(') or l.startswith('_ail_ta_shapes')]
        self.assertEqual(got, want, fu)

    def test_the_same_shape_shares_a_function(self):
        text = lowered(HEAD + 'def f(%s):\n    return (a * b + a, b * c + b, ta.sum(a * b), ta.sum(b * c))\n' % F)
        self.assertEqual(len(functions(text, '_ail_taf_fu')), 1)
        self.assertEqual(len(functions(text, '_ail_taf_fs')), 1)

    def test_a_call_among_the_operands_is_not_reordered(self):
        src = HEAD + ('def g(a: ta.Array[ta.f64]) -> ta.Array[ta.f64]:\n    return a\n\n\n'
                      'def f(%s):\n    return (g(a) * b + g(b) * a, ta.sum(g(a) / b + c), ta.dot(b * c, g(a)))\n' % F)
        text = lowered(src)
        # no function fuses a call: the operands stay where they stood
        for fu in functions(text, '_ail_taf_fu').values():
            self.assertNotIn('g(', fu)
        self.assertEqual(text.count('g(a)'), 3, text)
        # each call is an argument of a generated single-operation function, in the place it had
        self.assertIn('_ail_taf_fu0(_ail_taf_fu1(g(a), b), _ail_taf_fu1(g(b), a))', text)
        self.assertIn('_ail_taf_dot(', text)             # the second operand of a dot is not moved before the checks of the first

    def test_sum_and_dot_have_no_array_of_n_elements(self):
        text = lowered(HEAD + 'def f(%s):\n    return (ta.sum(a * b + c), ta.dot(a, b * c), ta.dot(a + b, c / a))\n' % F)
        self.assertNotIn('_ail_taf_bin', text)
        self.assertNotIn('_ail_taf_sum(', text)
        self.assertNotIn('_ail_taf_dot(', text)
        for body in functions(text, '_ail_taf_fs').values():
            self.assertIn('_ail_ta_bsum(buf)', body)
            self.assertIn('buf = _AilTAF(', body)
            self.assertNotIn('_AilTAF(n)', body)
        self.assertEqual(len(functions(text, '_ail_taf_fd')), 2)

    def test_a_plain_sum_and_dot_use_the_unrolled_lanes(self):
        text = lowered(HEAD + 'def f(%s):\n    return (ta.sum(a), ta.dot(a, b))\n' % F)
        for name in ('_ail_taf_fsum_s', '_ail_taf_fsum_d'):
            body = functions(text, name)[name]
            self.assertNotIn('% 16', body)
            self.assertIn('l15 = l15 + ', body)

    def test_in_place_forms(self):
        text = lowered(HEAD + 'def f(%s):\n    a += b * c\n    a -= b / c\n    a *= 2.0\n    return a\n' % F)
        self.assertEqual(len(functions(text, '_ail_taf_fi')), 2)
        self.assertIn('a = _ail_taf_fi0(a, b, c)', text)
        self.assertIn('_ail_taf_ibin_s(', text)            # `a *= 2.0` is one operation: T2's loop
        body = list(functions(text, '_ail_taf_fk').values())[0]
        self.assertIn('a0.d[k] = ', body)
        self.assertNotIn('_AilTAF(', body)
        self.assertIn('-> None', body)                 # the IR does not compile a function that returns an array

    def test_a_chain_of_256_operations_does_not_nest(self):
        e = 'a'
        for i in range(128):
            e = '(%s * b + c)' % e
        text = lowered(HEAD + 'def f(%s):\n    return %s\n' % (F, e))
        self.assertEqual(len(functions(text, '_ail_taf_fu')), 1)
        ast.parse(text)

    def test_a_function_never_holds_more_than_256_operations(self):
        e = 'a'
        for i in range(130):
            e = '(%s * b + c)' % e                      # 260 operations: cut at the top operation, the rest in functions of their own
        text = lowered(HEAD + 'def f(%s):\n    return %s\n' % (F, e))
        kernels = functions(text, '_ail_taf_fk')
        self.assertGreaterEqual(len(kernels), 3)
        for body in kernels.values():
            self.assertLessEqual(len(re.findall(r'^\s+t\d+ = (?!nan)', body, re.M)), 256)


# ---------------------------------------------------------------------------------------------------------------------
class Reference:
    """The output of CPython running a case program with the T1 reference, once."""

    def __init__(self, directory):
        self.dir = Path(directory)
        (self.dir / 'ref').mkdir()
        shutil.copy(ROOT / 'ail_array.py', self.dir / 'ref' / 'ail_array.py')
        self.want = {}

    def get(self, name):
        if name not in self.want:
            (self.dir / 'ref' / (name + '.py')).write_text((CASES / (name + '.py')).read_text(encoding='utf-8'), encoding='utf-8')
            r = subprocess.run([sys.executable, '-B', name + '.py'], cwd=self.dir / 'ref', capture_output=True, text=True,
                               env=clean_env(), timeout=1800)
            self.want[name] = (r.stdout, r.returncode)
        return self.want[name]


class Bits(unittest.TestCase):
    """The lowered text, run by CPython, prints what the reference prints (white box: no C compiler involved)."""

    @classmethod
    def setUpClass(cls):
        cls._tmp = tempfile.TemporaryDirectory(prefix='ail-fuse-bits-')
        cls.dir = Path(cls._tmp.name)
        cls.ref = Reference(cls.dir)

    @classmethod
    def tearDownClass(cls):
        cls._tmp.cleanup()

    def check(self, name, gpu_build):
        source = (CASES / (name + '.py')).read_text(encoding='utf-8')
        path = self.dir / ('low_%s_%d.py' % (name, gpu_build))
        path.write_text(lowered(source, gpu_build), encoding='utf-8')
        got = subprocess.run([sys.executable, '-B', str(path)], capture_output=True, text=True, env=clean_env(), timeout=1800)
        self.assertEqual((got.stdout, got.returncode), self.ref.get(name), got.stderr[-800:])

    def test_default_lowering(self):
        for name in NAMES:
            with self.subTest(case=name):
                self.check(name, False)


@unittest.skipUnless(CC, 'no C compiler')
class Programs(unittest.TestCase):
    """The compiled programs: default build and AIL_UNIFIED_FORCE=1 (every function through the general path)."""

    @classmethod
    def setUpClass(cls):
        cls._tmp = tempfile.TemporaryDirectory(prefix='ail-fuse-prog-')
        cls.dir = Path(cls._tmp.name)
        cls.ref = Reference(cls.dir)
        cls.builds = {}

    @classmethod
    def tearDownClass(cls):
        cls._tmp.cleanup()

    def build(self, name, unified=False, gpu_build=False):
        key = (name, unified, gpu_build)
        if key not in self.builds:
            tag = '%s_%s%s' % (name, 'u' if unified else 'd', 'g' if gpu_build else '')
            env = clean_env()
            if unified:
                env['AIL_UNIFIED_FORCE'] = '1'
            else:
                env['AIL_NO_GENERAL'] = '1'                        # the typed path or an error: a fall-back would hide a slow loop
            src = self.dir / (tag + '.py')
            src.write_text((CASES / (name + '.py')).read_text(encoding='utf-8'), encoding='utf-8')
            exe = self.dir / (tag + '.exe')
            cmd = [sys.executable, '-B', str(CLI), 'compile', str(src), '-o', str(exe), '--no-cache', '--debug-dir', str(self.dir / (tag + '.dbg'))]
            if gpu_build:
                cmd.append('--gpu')
            r = subprocess.run(cmd, capture_output=True, text=True, env=env, timeout=1800)
            self.builds[key] = (r, exe, self.dir / (tag + '.dbg') / 'program.c')
        return self.builds[key]

    def run_case(self, name, **kw):
        r, exe, _ = self.build(name, **{k: v for k, v in kw.items() if k in ('unified', 'gpu_build')})
        self.assertEqual(r.returncode, 0, r.stderr[-1500:])
        env = clean_env()
        env.update({k: v for k, v in kw.items() if k.startswith('AIL_')})
        got = subprocess.run([str(exe)], capture_output=True, text=True, env=env, timeout=1800)
        self.assertEqual((got.stdout, got.returncode), self.ref.get(name), (name, kw, got.stderr[-500:]))

    def test_default_build(self):
        for name in NAMES:
            with self.subTest(case=name):
                self.run_case(name)

    def test_unified_force_build(self):
        for name in NAMES:
            with self.subTest(case=name):
                self.run_case(name, unified=True)

    def test_the_kernels_are_ir_loops_not_the_legacy_emitter(self):
        """A generated function that fell out of the IR path would be correct and 3 times slower: look for the IR clone of each kernel."""
        for name in ('chains', 'reduce', 'inplace'):
            with self.subTest(case=name):
                r, exe, c = self.build(name)
                self.assertEqual(r.returncode, 0, r.stderr[-1500:])
                text = c.read_text(encoding='utf-8')
                kernels = set(re.findall(r'\bpy__ail_taf_fk(\d+)\(', text))
                self.assertTrue(kernels or name != 'chains')
                for k in kernels if name != 'inplace' else ():        # an in-place kernel returns nothing: no list clone
                    self.assertIn('py__ail_taf_fk%s__irl(' % k, text)
                for kind in ('fi', 'fs', 'fd'):
                    for m in set(re.findall(r'\bpy__ail_taf_%s(\d+)\(' % kind, text)):
                        self.assertRegex(text, r'ir\d+_p\[ir\d+\] = ', kind)             # an unchecked store in a guarded loop


if __name__ == '__main__':
    unittest.main()
