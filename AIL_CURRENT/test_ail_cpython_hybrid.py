"""`ail build --cpython`: typed functions in a CPython extension, everything else in CPython.

The hybrid is explicit (the flag is new; the standalone build is untouched).  For a program whose
functions are typed-compilable, the generated extension is loaded and the Python module output must
equal CPython byte for byte, including the cases that must abandon the native call: an int outside
int64, an overflow inside the clone, a bool in an int/list[int] position, a missing argument
(default), None, and a mutated list parameter.  Functions whose body can trap in the typed runtime
(indexing, division, calls, raise/try) stay in CPython; that includes `first` and `half` here.  A
program the compiler cannot analyse at all still runs unchanged in CPython with no extension.
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


PROGRAM = '''
def add1(n: int) -> int:
    return n + 1

def mul(n: int) -> int:
    return n * n

def isbig(n: int) -> bool:
    return n > 10

def half(x: float) -> float:
    return x / 2

def join(a: str, b: str) -> str:
    return a + b

def total(xs: list[int]) -> int:
    s = 0
    for x in xs:
        s += x
    return s

def first(xs: list[int]) -> int:
    return xs[0]

def push(xs: list[int]) -> int:
    xs.append(9)
    return len(xs)

def divide(a: int, b: int) -> int:
    return a // b

def dflt(n: int = 3) -> int:
    return n * 2

def echo(x: int) -> int:
    return x

BIG = int('1180591620717411303424')
HUGE = int('1267650600228229401496703205376')
print('add', add1(5), add1(BIG))
print('mul', mul(2**40), mul(-2**40))
print('bool', isbig(20), isbig(-1), isbig(HUGE))
print('float', half(3.0), half(-0.0), half(float('inf')))
print('str', join('a', 'b'), join('héllo 東京', '!'), join('', ''))
print('list', total([1, 2, 3]), total([]), total([2**62, 2**62]), total([True, 2]))
print('first', first([True]), first([BIG]), first([7]))
xs = [1, 2]
print('mut', push(xs), xs)
for a, b in ((7, 2), (7, 0), (-7, 2)):
    try:
        print('div', divide(a, b))
    except Exception as e:
        print('div-exc', type(e).__name__, e)
print('dflt', dflt(), dflt(4), dflt(n=5))
print('echo', echo(True), echo(HUGE))
'''

REFUSED = '''
import datetime


def days(a, b):
    return (b - a).days


print(days(datetime.date(2024, 1, 1), datetime.date(2024, 1, 31)))
'''


def run(cmd, cwd=None, stdin=''):
    return subprocess.run(cmd, cwd=cwd, input=stdin.encode(), capture_output=True, timeout=600)


@unittest.skipUnless(HAVE_CC and HAVE_HEADERS, 'needs a C compiler and the CPython headers')
class CPythonHybrid(unittest.TestCase):
    def build(self, tmp, name, text):
        src = Path(tmp) / (name + '.py')
        src.write_text(text, encoding='utf-8')
        out = Path(tmp) / 'out'
        env = dict(os.environ, AIL_NO_CACHE='1')
        built = run([sys.executable, '-B', CLI, 'build', '--cpython', str(src), '-o', str(out)], tmp)
        self.assertEqual(built.returncode, 0, built.stderr[-3000:])
        report = json.loads((out / 'build.json').read_text(encoding='utf-8'))
        return src, out, report

    def test_accelerated_and_fallbacks(self):
        with tempfile.TemporaryDirectory(prefix='ail-cpython-hybrid-') as tmp:
            src, out, report = self.build(tmp, 'prog', PROGRAM)
            self.assertTrue(report['extension'], report)
            accelerated = set(report['accelerated'])
            for name in ('add1', 'mul', 'isbig', 'join', 'total', 'dflt', 'echo'):
                self.assertIn(name, accelerated)
            self.assertNotIn('first', accelerated)         # indexing can raise IndexError
            self.assertNotIn('half', accelerated)           # division can raise ZeroDivisionError
            self.assertNotIn('push', accelerated)          # a list parameter that is mutated
            self.assertNotIn('divide', accelerated)        # floor division can raise
            want = run([sys.executable, str(src)], tmp)
            got = run([str(out / 'prog')], tmp)
            self.assertEqual(got.stdout, want.stdout)
            self.assertEqual(got.returncode, want.returncode)
            # the launcher needs a CPython at run time, and the original is kept beside the hybrid copy
            self.assertTrue((out / 'prog.orig.py').is_file())
            self.assertTrue((out / 'prog.py').is_file())

    def test_unanalysable_program_runs_in_cpython(self):
        with tempfile.TemporaryDirectory(prefix='ail-cpython-hybrid-') as tmp:
            src, out, report = self.build(tmp, 'refused', REFUSED)
            self.assertEqual(report['accelerated'], [])
            self.assertFalse(report['extension'])
            want = run([sys.executable, str(src)], tmp)
            got = run([str(out / 'refused')], tmp)
            self.assertEqual(got.stdout, want.stdout)
            self.assertEqual(got.returncode, want.returncode)


if __name__ == '__main__':
    unittest.main()
