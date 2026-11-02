"""prog14: the hot helpers of eight real programs reach the typed path (hybrid build), against CPython 3.12.

Two reasons used to keep the time-dominating functions of these programs out of the hybrid's typed
set:

* `pymix` did not infer tuple assignments (`a, b = b, (a + b) % MOD`) and its candidacy slice dropped
  literal module constants, so t341's `count_valid` was "unresolved-return" (and would have then
  read `MOD` before it was assigned).
* the hybrid body gate refused every `%`/`//`/`/` and every call, so g02_002's
  `proper_divisor_sum` was marked "division or power can raise", and `range(...)` in `count_valid`
  was "a call can raise or have side effects".

The gate now accepts a division whose divisor is a positive literal, a local every binding keeps
positive (`i = 2; i += 1`), or a nonzero literal module constant, and accepts `range`/`len` while
those names are the builtins.  A divisor passed as a parameter, or a literal zero/negative, still
stays in CPython; no int is wrapped.

P1  g02_002: `proper_divisor_sum` is accelerated and the program matches CPython.
P2  t341: `count_valid` is accelerated and several stdin values match CPython.
P3  the gate's boundaries: constant/local/module-constant divisors and `len` are accelerated;
    parameter/zero/negative divisors are not, and their calls still match CPython (including the
    ZeroDivisionError from `% 0`).
P4  a module name rebound after its literal (`MOD += -4`) is not a one-time constant, so its helper
    stays out; only a name bound exactly once is proven.  A parameter rebound under a branch is not
    a proven-positive local.  Both programs still match CPython.
P5  a constant bound after the first call (CPython raises `NameError`) is not kept, a `range` with
    a zero step is refused so the clone cannot raise outside CPython, and `len(range(a, b))`
    matches CPython when `a > b` and when the bound is negative.
P6  an annotated module literal (`LIMIT: int = 100`) is a one-time module constant too, even when
    the Python surface leaves a `pass` before it (g25_012's lowered `match` source); the helper
    that reads it is accelerated and the program matches CPython.
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
CLI = str(ROOT / 'ail_chatgpt.py')
HAVE_CC = shutil.which(os.environ.get('PIPE_CC') or 'gcc') is not None
HAVE_HEADERS = (Path(sysconfig.get_paths().get('include', '/nonexistent')) / 'Python.h').is_file()

G02 = ROOT.parent / 'lab' / 'census' / 'programs' / 'gdev' / 'g02_002.py'
T341 = ROOT.parent / 'lab' / 'corpus' / 'programs' / 'glm-5.3-flash-free' / 't341.py'

DIVISION = '''
MOD = 7


def by_const(n: int) -> int:
    return n % MOD


def by_three(n: int) -> int:
    return n // 3


def by_local(n: int) -> int:
    i = 2
    while i * i <= n:
        i += 1
    return n % i


def by_param(n: int, d: int) -> int:
    return n % d


def by_zero(n: int) -> int:
    return n % 0


def by_negative_local(n: int) -> int:
    d = -2
    return n % d


def count(xs: list[int]) -> int:
    return len(xs)


print(by_const(10), by_const(-10), by_three(10), by_three(-10), by_local(10), by_local(0))
print(by_param(10, 3), by_param(10, -3))
print(count([]), count([1, 2, 3]))
try:
    print(by_zero(3))
except ZeroDivisionError as e:
    print('zero', type(e).__name__, e)
try:
    print(by_negative_local(3))
except Exception as e:
    print('negative', type(e).__name__, e)
'''


REBIND = '''
MOD_AUG = 7
MOD_AUG += -4
MOD_ONCE = 7


def by_aug(n: int) -> int:
    return n % MOD_AUG


def by_once(n: int) -> int:
    return n % MOD_ONCE


print(by_aug(10), by_once(10))
'''

PARAM = '''
def by_param(n: int, i: int) -> int:
    if n:
        i = 2
    return n % i


print(by_param(10, 0))
try:
    print(by_param(0, 0))
except ZeroDivisionError as e:
    print(type(e).__name__, e)
'''


LATE_CONSTANT = '''
def f(n: int) -> int:
    return n % MOD


print(f(10))
MOD = 7
'''


RANGE_ZERO = '''
def f(n: int) -> int:
    total = 0
    for i in range(0, n, 0):
        total += i
    return total


try:
    print(f(5))
except ValueError as e:
    print('VE', e)
'''


RANGE_LEN = '''
def f(n: int) -> int:
    r = range(n)
    return len(r)


def g(a: int, b: int) -> int:
    return len(range(a, b))


def h(n: int) -> int:
    return len(range(0, n, 2))


def k(n: int) -> int:
    return len(range(n, 0, -2))


print(f(5), f(-3))
print(g(0, 5), g(5, 0), g(-3, 2), g(2, -3))
print(h(5), h(0), h(-4))
print(k(5), k(0), k(-4))
'''


ANNOTATED_CONSTANT = '''
pass
LIMIT: int = 100
MOD: int = 7


def classify(n: int) -> int:
    if n <= LIMIT:
        return n % MOD
    return -1


print(classify(10), classify(100), classify(101))
'''


def run(cmd, cwd=None, stdin=b'', env=None):
    return subprocess.run(cmd, cwd=cwd, input=stdin, env=env, capture_output=True, timeout=600)


@unittest.skipUnless(HAVE_CC and HAVE_HEADERS, 'needs a C compiler and the CPython headers')
class Prog14(unittest.TestCase):
    def build(self, tmp, source, name):
        """Build `source` (a path) with the CPython hybrid and return (source path, launcher, report)."""
        out = Path(tmp) / ('out_' + name)
        built = run([sys.executable, '-B', CLI, 'build', '--cpython', str(source), '-o', str(out)],
                    tmp, env=dict(os.environ, AIL_NO_CACHE='1'))
        self.assertEqual(built.returncode, 0, built.stderr[-3000:])
        report = json.loads((out / 'build.json').read_text(encoding='utf-8'))
        return source, out / Path(source).stem, report

    def compare(self, source, launcher, stdin=b''):
        want = run([sys.executable, str(source)], stdin=stdin)
        got = run([str(launcher)], stdin=stdin)
        self.assertEqual(got.stdout, want.stdout)
        self.assertEqual(got.returncode, want.returncode)
        if want.returncode:
            self.assertTrue(got.stderr.strip())
        return want

    def test_proper_divisor_sum_accelerated(self):
        with tempfile.TemporaryDirectory(prefix='ail-prog14-g02-') as tmp:
            source, launcher, report = self.build(tmp, G02, 'g02')
            self.assertIn('proper_divisor_sum', report['accelerated'], report)
            self.compare(source, launcher)

    def test_count_valid_accelerated(self):
        with tempfile.TemporaryDirectory(prefix='ail-prog14-t341-') as tmp:
            source, launcher, report = self.build(tmp, T341, 't341')
            self.assertIn('count_valid', report['accelerated'], report)
            for stdin in (b'0\n', b'1\n', b'30\n', b'100000\n'):
                self.compare(source, launcher, stdin)

    def test_division_and_call_boundaries(self):
        with tempfile.TemporaryDirectory(prefix='ail-prog14-div-') as tmp:
            source = Path(tmp) / 'division.py'
            source.write_text(DIVISION, encoding='utf-8')
            src, launcher, report = self.build(tmp, source, 'division')
            accelerated = set(report['accelerated'])
            for name in ('by_const', 'by_three', 'by_local', 'count'):
                self.assertIn(name, accelerated, report)
            for name in ('by_param', 'by_zero', 'by_negative_local'):
                self.assertNotIn(name, accelerated, report)
            # `% 0` runs in CPython (nothing wraps or guesses) and both runs print the same text.
            self.compare(src, launcher)

    def test_rebound_constant_and_parameter_are_not_proven(self):
        with tempfile.TemporaryDirectory(prefix='ail-prog14-rebind-') as tmp:
            for name, text in (('rebind', REBIND), ('param', PARAM)):
                source = Path(tmp) / (name + '.py')
                source.write_text(text, encoding='utf-8')
                src, launcher, report = self.build(tmp, source, name)
                accelerated = set(report['accelerated'])
                if name == 'rebind':
                    self.assertIn('by_once', accelerated, report)
                    self.assertNotIn('by_aug', accelerated, report)
                else:
                    self.assertNotIn('by_param', accelerated, report)
                self.compare(src, launcher)

    def test_late_constant_and_range_boundaries(self):
        with tempfile.TemporaryDirectory(prefix='ail-prog14-boundary-') as tmp:
            expected = {
                ('late', LATE_CONSTANT): set(),
                ('zero', RANGE_ZERO): set(),
                ('len', RANGE_LEN): {'f', 'g', 'h', 'k'},
            }
            for (name, text), wanted in expected.items():
                source = Path(tmp) / (name + '.py')
                source.write_text(text, encoding='utf-8')
                src, launcher, report = self.build(tmp, source, name)
                self.assertEqual(set(report['accelerated']), wanted, report)
                self.compare(src, launcher)

    def test_annotated_module_constant(self):
        with tempfile.TemporaryDirectory(prefix='ail-prog14-annconst-') as tmp:
            source = Path(tmp) / 'annotated.py'
            source.write_text(ANNOTATED_CONSTANT, encoding='utf-8')
            src, launcher, report = self.build(tmp, source, 'annotated')
            self.assertIn('classify', report['accelerated'], report)
            self.compare(src, launcher)


if __name__ == '__main__':
    unittest.main()
