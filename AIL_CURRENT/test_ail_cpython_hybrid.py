"""`ail build --cpython`: typed functions in a CPython extension, everything else in CPython.

The hybrid is explicit (the flag is new; the standalone build is untouched).  For a program whose
functions are typed-compilable, the generated extension is loaded and the Python module output must
equal CPython byte for byte, including the cases that must abandon the native call: an int outside
int64, an overflow inside the clone, a bool in an int/list[int] position, a missing argument
(default), None, and a mutated list parameter.  Functions whose body can trap in the typed runtime
(indexing, division by a variable, calls, raise/try) stay in CPython; that includes `first` and
`divide` here.  A division by a literal nonzero constant (`half`, `x / 2`) cannot raise and is
eligible.  A program the compiler cannot analyse at all still runs unchanged in CPython with no
extension.
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


def run(cmd, cwd=None, stdin='', env=None):
    return subprocess.run(cmd, cwd=cwd, input=stdin.encode(), env=env,
                          capture_output=True, timeout=600)


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
            for name in ('add1', 'mul', 'isbig', 'half', 'join', 'total', 'dflt', 'echo'):
                self.assertIn(name, accelerated)
            self.assertNotIn('first', accelerated)         # indexing can raise IndexError
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

    def test_two_list_fallback(self):
        text = '''
def f(a: list[int], b: list[int]) -> int:
    return 0

print(f([1.5], [2]))
print(f([1], [2.5]))
print(f([1], [2]))
'''
        with tempfile.TemporaryDirectory(prefix='ail-cpython-hybrid-') as tmp:
            src, out, report = self.build(tmp, 'twolists', text)
            self.assertIn('f', report['accelerated'])
            want = run([sys.executable, str(src)], tmp)
            got = run([str(out / 'twolists')], tmp)
            self.assertEqual(got.stdout, want.stdout)
            self.assertEqual(got.returncode, want.returncode)

    def compare_imported(self, tmp, out, runner_text):
        runner = Path(tmp) / 'runner.py'
        runner.write_text(runner_text, encoding='utf-8')
        want = run([sys.executable, str(runner)], tmp,
                   env=dict(os.environ, PYTHONPATH=str(tmp)))
        got = run([sys.executable, str(runner)], tmp,
                  env=dict(os.environ, PYTHONPATH=str(out)))
        self.assertEqual(got.stdout, want.stdout)
        self.assertEqual(got.returncode, want.returncode)
        return got

    def test_accelerated_metadata(self):
        text = '''
def f(n: int) -> int:
    z = n + 1
    w = z * 2
    return w

def g(n: int = 7) -> int:
    return n * 2

def h(_ail_hybrid_invoke: int, _ail_hybrid_native_ref: int,
      _ail_hybrid_original_ref: int) -> int:
    return _ail_hybrid_invoke + _ail_hybrid_native_ref + _ail_hybrid_original_ref

def k(__ail_hybrid_invoke: int, __ail_hybrid_native_ref: int,
      __ail_hybrid_original_ref: int) -> int:
    return __ail_hybrid_invoke + __ail_hybrid_native_ref + __ail_hybrid_original_ref
'''
        runner = '''
import inspect
import metadata as m
print(m.f.__annotations__)
print(m.f.__defaults__)
print(m.f.__code__.co_argcount, m.f.__code__.co_varnames, m.f.__code__.co_name)
print(hasattr(m.f, '__wrapped__'), inspect.signature(m.f))
print(m.f(4), m.g(), m.g(4), m.g(n=5), m.h(1, 2, 3), m.k(4, 5, 6))
'''
        with tempfile.TemporaryDirectory(prefix='ail-cpython-hybrid-') as tmp:
            src, out, report = self.build(tmp, 'metadata', text)
            for name in ('f', 'g', 'h', 'k'):
                self.assertIn(name, report['accelerated'])
            self.compare_imported(tmp, out, runner)

    def test_fallback_from_later_arguments_releases_buffers(self):
        text = '''
def f(a: list[int], b: list[int]) -> int:
    return 0

def g(a: list[int], n: int) -> int:
    return n

def h(a: list[int], s: str) -> int:
    return 0
'''
        runner = '''
import fallbackbuf as m
for _ in range(20000):
    m.f([0] * 100, (2,))
    m.g([0] * 100, 2**100)
    m.h([0] * 100, 3)
print(m.f([1], [2]), m.g([1], 3), m.h([1], 'x'))
'''
        with tempfile.TemporaryDirectory(prefix='ail-cpython-hybrid-') as tmp:
            src, out, report = self.build(tmp, 'fallbackbuf', text)
            for name in ('f', 'g', 'h'):
                self.assertIn(name, report['accelerated'])
            self.compare_imported(tmp, out, runner)

    def test_concurrent_overflow_falls_back_per_thread(self):
        text = '''
def mul(n: int) -> int:
    return n * n
'''
        runner = '''
import threading
import threaded as m
values = [3037000500, 2**40, 3, -4, 2**62, 7]
def work():
    for i in range(2000):
        n = values[i % len(values)]
        assert m.mul(n) == n * n

threads = [threading.Thread(target=work) for _ in range(8)]
for t in threads:
    t.start()
for t in threads:
    t.join()
print('threads-ok')
'''
        with tempfile.TemporaryDirectory(prefix='ail-cpython-hybrid-') as tmp:
            src, out, report = self.build(tmp, 'threaded', text)
            self.assertIn('mul', report['accelerated'])
            got = self.compare_imported(tmp, out, runner)
            self.assertEqual(got.returncode, 0)
            self.assertIn(b'threads-ok', got.stdout)

    def test_file_and_sibling_import_survive_packaging(self):
        text = '''
import os
import sys
import helper_mod

def f(n: int) -> int:
    return n + 1

print(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data.txt')).read().strip())
print(helper_mod.VALUE)
print(os.path.abspath(__file__))
print(os.path.abspath(sys.argv[0]))
print(f(1))
'''
        with tempfile.TemporaryDirectory(prefix='ail-cpython-hybrid-') as tmp:
            (Path(tmp) / 'helper_mod.py').write_text("VALUE = 'sibling-ok'\n", encoding='utf-8')
            (Path(tmp) / 'data.txt').write_text('hello\n', encoding='utf-8')
            src, out, report = self.build(tmp, 'paths', text)
            want = run([sys.executable, str(src)], tmp)
            got = run([str(out / 'paths')], tmp)
            self.assertEqual(got.stdout, want.stdout)
            self.assertEqual(got.returncode, want.returncode)


if __name__ == '__main__':
    unittest.main()
