"""Typed reach for the hot functions of eight real programs (job-prog4), against CPython 3.12.

The CPython hybrid accelerates only a function the real mixed-mode emitter accepts.  The hot helper
in `lab/census/programs/dev/t024.py` is `is_prime`: its `%` and `//` were refused by the hybrid's
extra body gate even though `pymix` had already proved that a trap cannot reach a boxed handler.
That gate now allows division/modulo, and a slice only when its step is a constant non-zero integer
(step 0 is CPython's ValueError; a run-time step is left to CPython), so `is_prime`, `mod7`,
`divmod7` and the safe slice helpers gain a typed clone while the rest of each program stays in
CPython.

T1  `is_prime` is named in the hybrid's accelerated list.
T2  the hybrid program prints CPython's stdout and exit status on every public input.
T3  division/modulo boundaries (zero, negative, bool, int64 edges) and a safe slice run natively;
    a variable or zero slice step is not accelerated and falls back to CPython's exception.
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
T024 = ROOT.parent / 'lab' / 'census' / 'programs' / 'dev' / 't024.py'
T024_INPUTS = [ROOT.parent / 'lab' / 'corpus' / 'tasks' / 't024' / ('in%d.txt' % i) for i in range(3)]
HAVE_CC = shutil.which(os.environ.get('PIPE_CC') or 'gcc') is not None
HAVE_HEADERS = (Path(sysconfig.get_paths().get('include', '/nonexistent')) / 'Python.h').is_file()

DIVMOD = '''
def mod7(x: int) -> int:
    return x % 7

def divmod7(x: int) -> int:
    return (x % 7) + (x // 7)

def mod(x: int, y: int) -> int:
    return x % y

def fdiv(x: int, y: int) -> int:
    return x // y

def tdiv(x: float, y: float) -> float:
    return x / y

class Box:
    def __init__(self, n):
        self.n = n

values = [0, 1, -1, 7, -7, 8, 2**40, -2**40, 2**62, -(2**62),
          2**63 - 1, -(2**63), True, False]
for v in values:
    print('dict', mod7(v), divmod7(v))
print('through-arg', mod7(Box(22).n))
print('through-list', mod7([13, 21][1]))
print('through-dict', mod7({'k': 15}['k']))
print('through-attr', mod7(Box(-15).n))
for a, b in ((8, 3), (-8, 3), (8, -3), (-8, -3), (0, 5)):
    print('ints', a, b, mod(a, b), fdiv(a, b))
for a, b in ((7.5, 2.5), (-7.5, 2.5), (0.0, 4.0)):
    print('floats', a, b, tdiv(a, b))
for a, b in ((1, 0), (1.0, 0.0)):
    for fn in (mod, fdiv, tdiv):
        try:
            print('zero', fn(a, b))
        except Exception as exc:
            print('zero-exc', type(exc).__name__, exc)
'''

SLICES = '''
def middle_sum(xs: list[int]) -> int:
    s = 0
    for v in xs[1:-1]:
        s += v
    return s

def reverse_sum(xs: list[int]) -> int:
    s = 0
    for v in xs[::-1]:
        s += v
    return s

def every_other(xs: list[int]) -> int:
    s = 0
    for v in xs[::2]:
        s += v
    return s

def head2(s: str) -> str:
    return s[:2]

def back(s: str) -> str:
    return s[::-1]

def variable_step(xs: list[int], k: int) -> int:
    s = 0
    for v in xs[::k]:
        s += v
    return s

def zero_step(xs: list[int]) -> int:
    s = 0
    for v in xs[::0]:
        s += v
    return s

for xs in ([], [5], [1, 2, 3, 4, 5], [-1, -2, -3], [2**40, 1, 2**40]):
    print('sums', middle_sum(xs), reverse_sum(xs), every_other(xs))
alias = [9, 8, 7]
print('alias', middle_sum(alias), alias)
print('through-arg', reverse_sum([4, 5, 6]))
print('through-list', every_other([[1], [2, 3, 4]][1]))
print('through-dict', middle_sum({'k': [10, 20, 30, 40]}['k']))
for text in ('', 'a', 'hello', 'héllo 東京'):
    print('str', head2(text), back(text))
print('str-through-list', head2(['ab', 'cde'][1]))
print('str-through-dict', back({'k': 'abc'}['k']))
for k in (1, 2, -1, -2):
    print('var', k, variable_step([1, 2, 3, 4, 5], k))
try:
    print('var', 0, variable_step([1, 2, 3], 0))
except Exception as exc:
    print('var-exc', type(exc).__name__, exc)
try:
    print('zero', zero_step([1, 2, 3]))
except Exception as exc:
    print('zero-exc', type(exc).__name__, exc)
'''


def run(cmd, cwd=None, stdin=b'', env=None):
    return subprocess.run(cmd, cwd=cwd, input=stdin, env=env, capture_output=True, timeout=900)


@unittest.skipUnless(HAVE_CC and HAVE_HEADERS, 'needs a C compiler and the CPython headers')
class Prog4TypedReach(unittest.TestCase):
    def build(self, tmp, name, source):
        src = Path(tmp) / (name + '.py')
        src.write_text(source, encoding='utf-8')
        out = Path(tmp) / (name + '_out')
        env = dict(os.environ, AIL_NO_CACHE='1')
        built = run([sys.executable, '-B', CLI, 'build', '--cpython', str(src), '-o', str(out)], tmp,
                    env=env)
        self.assertEqual(built.returncode, 0, built.stderr[-3000:])
        report = json.loads((out / 'build.json').read_text(encoding='utf-8'))
        return src, out, report

    def compare(self, tmp, src, out, name, stdin=b''):
        want = run([sys.executable, str(src)], tmp, stdin=stdin)
        got = run([str(out / name)], tmp, stdin=stdin)
        self.assertEqual(got.stdout, want.stdout, name)
        self.assertEqual(got.returncode, want.returncode, name)
        return got

    def test_is_prime_is_accelerated_and_matches_cpython(self):
        with tempfile.TemporaryDirectory(prefix='ail-prog4-') as tmp:
            source = T024.read_text(encoding='utf-8')
            src, out, report = self.build(tmp, 't024', source)
            self.assertIn('is_prime', report['accelerated'])
            for path in T024_INPUTS:
                self.compare(tmp, src, out, 't024', path.read_bytes())

    def test_division_and_modulo_are_accelerated(self):
        with tempfile.TemporaryDirectory(prefix='ail-prog4-') as tmp:
            src, out, report = self.build(tmp, 'divmod', DIVMOD)
            self.assertIn('mod7', report['accelerated'])
            self.assertIn('divmod7', report['accelerated'])
            self.compare(tmp, src, out, 'divmod')

    def test_slice_steps_are_safe(self):
        with tempfile.TemporaryDirectory(prefix='ail-prog4-') as tmp:
            src, out, report = self.build(tmp, 'slices', SLICES)
            for name in ('middle_sum', 'reverse_sum', 'every_other', 'head2', 'back'):
                self.assertIn(name, report['accelerated'])
            self.assertNotIn('variable_step', report['accelerated'])
            self.assertNotIn('zero_step', report['accelerated'])
            self.compare(tmp, src, out, 'slices')


if __name__ == '__main__':
    unittest.main()
