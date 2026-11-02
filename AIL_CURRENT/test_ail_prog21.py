"""Typed reach for the hot functions of the eight prog21 programs (2026-11-02).

The batch's untyped hot functions were blocked by three compiler rules:

* the CPython hybrid refused `abs(x)` even when `x` is an `int`/`float` parameter, so
  `shift_and_add_multiply` (the hot helper of `lab/census/programs/gdev/g22_022.py`) stayed in
  CPython.  `abs` of a float is `fabs`; `abs` of an int can only overflow on `INT64_MIN`, and an
  int/bool result routes that through the existing overflow wrapper back to CPython.
* `str(<number>)` cannot raise, and `int(<int/bool>)` is the identity, so those calls are safe in
  a clone too.  A unary `-`/`int(-x)` of an int can overflow on `INT64_MIN`, so it is accepted only
  when the clone returns int/bool (where the existing wrapper falls back to CPython); a str result
  has no such wrapper.  `int(<float>)` is deliberately still refused: NaN is a ValueError and a
  finite value outside int64 needs the overflow wrapper, which only int/bool results have.  That
  is why `t139.fmt` (`int(value)` on a float) stays in CPython.
* `g21_038.encode_rounded_floats` stays in CPython: pymix still reports `unresolved-return`
  because it does not prove `json.dumps(...)` returns a str (unchanged by this job).  Even with
  that proof, the body's `round(v, places)` (a variable `ndigits`) and `json.dumps` are calls the
  hybrid refuses as `a call can raise or have side effects`.

The remaining hot functions are named follow-ups in `lab/progfix/prog21.md`: the enum/dataclass
module table of `g25_016` and Decimal in `t419` need large new features; `t139.fmt` and
`g21_038.encode_rounded_floats` stay in CPython for the reasons above.
"""
import json
import os
import shutil
import subprocess
import sys
import sysconfig
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parent
LAB = REPO / 'lab'
CLI = ROOT / 'ail_chatgpt.py'
HAVE_CC = shutil.which(os.environ.get('PIPE_CC') or 'gcc') is not None
HAVE_HEADERS = (Path(sysconfig.get_paths().get('include', '/nonexistent')) / 'Python.h').is_file()

ABS = '''from dataclasses import dataclass


@dataclass
class Box:
    n: int


def mag(x: int) -> int:
    return abs(x)


def fmag(x: float) -> float:
    return abs(x)


def main() -> None:
    box = Box(-7)
    table = {"k": -9}
    xs = [-2, 3, -4]
    for n in (0, 5, -5, xs[0], xs[2], box.n, table["k"], -(2**63), 2**63 - 1,
              True, False):
        print(n, mag(n))
    for x in (0.0, -0.0, 2.5, -2.5, float("inf"), float("-inf"), float("nan")):
        print(repr(x), repr(fmag(x)))


if __name__ == "__main__":
    main()
'''

STRCONV = '''def label(x: float) -> str:
    return str(x)


def main() -> None:
    for x in (0.0, -0.0, 1.5, -2.25, float("inf"), float("-inf"), float("nan"),
              1e308, 1e-308):
        print(label(x))


if __name__ == "__main__":
    main()
'''

BOOLABS = '''def abs_bool(x: bool) -> int:
    return abs(x)


def abs_bool_assign(x: bool) -> int:
    y = abs(x)
    return y


def abs_bool_uadd(x: bool) -> int:
    return abs(+x)


def abs_bool_usub(x: bool) -> int:
    return abs(-x)


def abs_bool_after_int(x: bool) -> int:
    return abs(int(x))


def main() -> None:
    print(abs_bool(True), abs_bool_assign(True), abs_bool_uadd(True), abs_bool_usub(True),
          abs_bool_after_int(True))
    print(abs_bool(False), abs_bool_assign(False), abs_bool_uadd(False), abs_bool_usub(False),
          abs_bool_after_int(False))


if __name__ == "__main__":
    main()
'''


def run(cmd, cwd=None, stdin='', env=None, timeout=900):
    return subprocess.run(cmd, cwd=cwd, input=stdin, env=env, text=True,
                          capture_output=True, timeout=timeout)


def compile_default(directory, text, name):
    source, exe = Path(directory, name + '.py'), Path(directory, name + '_x')
    source.write_text(text, encoding='utf-8')
    env = dict(os.environ, AIL_NO_CACHE='1', AIL_SERVER='0')
    for key in ('AIL_NO_GENERAL', 'AIL_UNIFIED_FORCE', 'AIL_QUIET_FALLBACK'):
        env.pop(key, None)
    res = run([sys.executable, '-B', str(CLI), 'compile', source.name, '-o', exe.name],
              cwd=directory, env=env)
    return res, exe, source


def typed(res):
    return 'built on the general path' not in res.stderr


def build_hybrid(directory, text, name):
    source = Path(directory) / (name + '.py')
    source.write_text(text, encoding='utf-8')
    out = Path(directory) / (name + '_out')
    env = dict(os.environ, AIL_NO_CACHE='1', AIL_SERVER='0')
    res = run([sys.executable, '-B', str(CLI), 'build', '--cpython', str(source),
               '-o', str(out)], cwd=directory, env=env)
    report = None
    if res.returncode == 0 and (out / 'build.json').is_file():
        report = json.loads((out / 'build.json').read_text(encoding='utf-8'))
    return res, source, out, report


@unittest.skipUnless(HAVE_CC and HAVE_HEADERS, 'needs a C compiler and the CPython headers')
class Prog21Hybrid(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.mkdtemp(prefix='prog21_')

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def hybrid(self, text, name, stdin=''):
        res, source, out, report = build_hybrid(self.tmp, text, name)
        self.assertEqual(res.returncode, 0, res.stderr[-3000:])
        self.assertIsNotNone(report, res.stderr[-2000:])
        want = run([sys.executable, str(source)], stdin=stdin)
        got = run([str(out / name)], stdin=stdin)
        self.assertEqual(got.stdout, want.stdout, repr(stdin))
        self.assertEqual(got.returncode, want.returncode, repr(stdin))
        return report

    def check_program(self, relative, name, inputs=('',)):
        path = LAB / relative
        if not path.is_file():
            self.skipTest('lab is not part of this tree')
        text = path.read_text(encoding='utf-8')
        return self.hybrid(text, name, ''), text

    def test_abs_int_and_float_accelerated(self):
        report = self.hybrid(ABS, 'abs21')
        self.assertIn('mag', report['accelerated'])
        self.assertIn('fmag', report['accelerated'])

    def test_str_conversion_accelerated(self):
        report = self.hybrid(STRCONV, 'strconv21')
        self.assertIn('label', report['accelerated'])

    def test_abs_bool_operand_stays_in_cpython(self):
        # abs(True) is the int 1, but the typed clone of abs of a bool-typed value (including
        # +x and -x, which keep the bool kind) returns a bool, which prints True.  Only int()
        # converts it, so abs(<bool>) is refused while abs(int(<bool>)) stays accelerated.
        report = self.hybrid(BOOLABS, 'abs_bool21')
        reason = 'a call can raise or have side effects'
        for name in ('abs_bool', 'abs_bool_assign', 'abs_bool_uadd', 'abs_bool_usub'):
            self.assertNotIn(name, report['accelerated'])
            self.assertEqual(report['rejected'].get(name), reason)
        self.assertIn('abs_bool_after_int', report['accelerated'])

    def test_str_neg_overflow_only_with_int_result_wrapper(self):
        text = '''def neg_int_text(x: int) -> str:
    return str(-x)


def neg_int_identity(x: int) -> str:
    y = int(-x)
    return "nonneg" if y >= 0 else "neg"


def neg_float_text(x: float) -> str:
    return str(-x)


def main() -> None:
    for v in (-(2 ** 63), 2 ** 63 - 1, 0, 7, -7):
        print(neg_int_text(v), neg_int_identity(v))
    for x in (0.0, -0.0, 2.5, -2.5, float("inf"), float("-inf"), float("nan")):
        print(neg_float_text(x))


if __name__ == "__main__":
    main()
'''
        report = self.hybrid(text, 'str_neg21')
        reason = 'a call can raise or have side effects'
        self.assertNotIn('neg_int_text', report['accelerated'])
        self.assertEqual(report['rejected'].get('neg_int_text'), reason)
        self.assertNotIn('neg_int_identity', report['accelerated'])
        self.assertEqual(report['rejected'].get('neg_int_identity'), reason)
        self.assertIn('neg_float_text', report['accelerated'])

    def test_shift_and_add_multiply_accelerated(self):
        report, _ = self.check_program('census/programs/gdev/g22_022.py', 'g22_022')
        self.assertIn('shift_and_add_multiply', report['accelerated'])

    def test_g21_encode_stays_in_cpython(self):
        report, _ = self.check_program('census/programs/gdev/g21_038.py', 'g21_038')
        self.assertNotIn('encode_rounded_floats', report['accelerated'])

    def test_fmt_int_float_stays_in_cpython(self):
        text = (LAB / 'corpus/programs/deepseek-v4.1-flash-free/t139.py').read_text(
            encoding='utf-8')
        cases = ('', 'deposit acc1 2\nbalance acc1\nwithdraw acc1 5\nbalance acc1\n')
        for index, stdin in enumerate(cases):
            report = self.hybrid(text, 't139_%d' % index, stdin)
            self.assertNotIn('fmt', report['accelerated'])
            self.assertEqual(report['rejected'].get('fmt'),
                             'a call can raise or have side effects')


@unittest.skipUnless(HAVE_CC, 'needs a C compiler')
class Prog21TypedPrograms(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.mkdtemp(prefix='prog21_typed_')

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def check(self, relative, name, inputs=('',)):
        path = LAB / relative
        if not path.is_file():
            self.skipTest('lab is not part of this tree')
        text = path.read_text(encoding='utf-8')
        res, exe, source = compile_default(self.tmp, text, name)
        self.assertEqual(res.returncode, 0, res.stderr[-3000:])
        self.assertTrue(typed(res), 'fell back to the general path: ' + res.stderr[-1000:])
        for stdin in inputs:
            want = run([sys.executable, str(source)], stdin=stdin)
            got = run([str(exe)], stdin=stdin)
            self.assertEqual(got.stdout, want.stdout, repr(stdin))
            self.assertEqual(got.returncode, want.returncode, repr(stdin))

    def test_typed_hot_programs_match_cpython(self):
        self.check('census/programs/gdev/g22_014.py', 'g22_014')
        self.check('census/programs/gdev/g22_022.py', 'g22_022')
        self.check('census/programs/dev/t078.py', 't078',
                   ('', 'abc\n', 'héllo 東京\n', 'x\n'))
        self.check('census/programs/dev/t232.py', 't232',
                   ('3 4\n....\n.#.#\n....\n', '1 1\n#\n'))
        self.check('census/programs/gdev/g21_038.py', 'g21_038')
        self.check('corpus/programs/deepseek-v4.1-flash-free/t139.py', 't139',
                   ('', 'deposit acc1 2\nbalance acc1\n'))


if __name__ == '__main__':
    unittest.main()
