"""One silent wrong answer found by differential fuzzing match statements (DIFFERENCES C?-job-fuzz23-10230421-1).

A guard that reads a name the pattern binds must read that value, but the lowering only substituted
the name outside nested scopes: a comprehension target of the same name hid it, so
`case [x] if all(x == 9 for x in [1, 2])` matched [9] here and missed it in CPython. A free pattern
name inside a lambda was not substituted at all and raised NameError. The substitution now follows
Python's scopes (lambda parameters and comprehension targets shadow a pattern name, their free names
still see it), against CPython 3.12 on both builds.
"""
import shutil
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent
import sys
sys.path.insert(0, str(ROOT))
from test_ail_nested_functions import build, build_general, run_cpython, run_exe   # noqa: E402

HAVE_CC = shutil.which('gcc') is not None

COMP = '''def comp(v: list[int]) -> str:
    match v:
        case [x] if all(x == 9 for x in [1, 2]):
            return "comp-hit"
        case _:
            return "comp-miss"


def shadow(v: list[int]) -> str:
    match v:
        case [x] if [x for x in [x]] == [3]:
            return "sh-hit"
        case _:
            return "sh-miss"


print(comp([9]), comp([5]), comp([3]))
print(shadow([9]), shadow([5]), shadow([3]))
'''

GUARDS = '''def lam(v):
    match v:
        case [x] if (lambda z: z == x)(v[0]):
            return "lam-hit"
        case _:
            return "lam-miss"


def default(v):
    match v:
        case [x, y] if (lambda a=x: a + y)(0) == 5:
            return "def-hit"
        case _:
            return "def-miss"


for v in [[9], [5], [2, 3], [3, 2]]:
    print(v, lam(v), default(v))
'''


@unittest.skipUnless(HAVE_CC, 'needs gcc')
class GuardScopes(unittest.TestCase):
    def test_guard_scopes_print_what_cpython_prints(self):
        with tempfile.TemporaryDirectory(prefix='ail-fuzz23-') as tmp:
            for name, text, typed in (('comp', COMP, True), ('lambda', GUARDS, False)):
                want = run_cpython(tmp, text, name)
                self.assertEqual(want.returncode, 0, want.stderr)
                if typed:
                    for ir in ('0', '1'):
                        res, exe = build(tmp, text, name, ir=ir)
                        self.assertEqual(res.returncode, 0, '%s IR=%s: %s' % (name, ir, res.stderr[-2000:]))
                        got = run_exe(exe)
                        self.assertEqual((got.returncode, got.stdout), (0, want.stdout), '%s IR=%s' % (name, ir))
                res, exe = build(tmp, text, name, typed_only=False)
                self.assertEqual(res.returncode, 0, name + ': ' + res.stderr[-2000:])
                got = run_exe(exe)
                self.assertEqual((got.returncode, got.stdout), (0, want.stdout), name + ' default')
                res, exe = build_general(tmp, text, name)
                self.assertEqual(res.returncode, 0, name + ': ' + res.stderr[-2000:])
                got = run_exe(exe)
                self.assertEqual((got.returncode, got.stdout), (0, want.stdout), name + ' general')


if __name__ == '__main__':
    unittest.main()
