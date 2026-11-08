"""`ail build --cpython`: typed functions in a CPython extension, everything else in CPython.
The hybrid is explicit (the standalone build is untouched).  For a program whose functions are
typed-compilable, the generated extension is loaded and the Python module output must equal
CPython byte for byte, including the cases that must abandon the native call: an int outside
int64, an overflow inside the clone, a bool in an int/list[int] position, a missing argument
(default), None, and a mutated list parameter.  Functions whose body can trap in the typed runtime
(arbitrary calls, raise/try) stay in CPython.  `first` indexes `xs[0]`, but an out-of-range
index is detected and the Python wrapper re-runs the original, so it is native too; since obs5 a
zero divisor in `divide` is handled the same way (CPython re-runs and raises, even into a
`try/except` around the call).  A division by a literal nonzero constant
(`half`, `x / 2`) and a proved pure str method call cannot raise and are eligible.  A program the
compiler cannot analyse at all still runs unchanged in CPython with no extension.
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
            for name in ('add1', 'mul', 'isbig', 'half', 'join', 'total', 'first', 'dflt', 'echo',
                         'divide'):
                self.assertIn(name, accelerated)
            self.assertNotIn('push', accelerated)          # a list parameter that is mutated
            want = run([sys.executable, str(src)], tmp)
            got = run([str(out / 'prog')], tmp)
            self.assertEqual(got.stdout, want.stdout)
            self.assertEqual(got.returncode, want.returncode)
            # the launcher needs a CPython at run time, and the original is kept beside the hybrid copy
            self.assertTrue((out / 'prog.orig.py').is_file())
            self.assertTrue((out / 'prog_run.py').is_file())
            self.assertTrue((out / 'prog.py').is_file())

    def test_container_calls_keep_the_gil(self):
        """D4: a native call with a list argument keeps the GIL; scalar-only calls still release it."""
        import ail_cpython_hybrid as hybrid

        items = [
            {'name': 'scalar', 'mangled': 'f_scalar', 'params': [('x', 'int')], 'ret': 'int',
             'is_bool_ret': False},
            {'name': 'listed', 'mangled': 'f_listed',
             'params': [('x', 'int'), ('xs', 'list[int]')], 'ret': 'int', 'is_bool_ret': False},
            {'name': 'floats', 'mangled': 'f_floats',
             'params': [('xs', 'list[float]')], 'ret': 'float', 'is_bool_ret': False},
        ]
        src = hybrid._wrapper_source('m', items)
        scalar = src[src.index('ail_w_scalar'):src.index('ail_w_listed')]
        listed = src[src.index('ail_w_listed'):src.index('ail_w_floats')]
        floats = src[src.index('ail_w_floats'):]
        self.assertIn('Py_BEGIN_ALLOW_THREADS', scalar)
        self.assertNotIn('Py_BEGIN_ALLOW_THREADS', listed)
        self.assertNotIn('Py_BEGIN_ALLOW_THREADS', floats)

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

    def test_index_and_dict_fallbacks(self):
        """A successful index is native; an IndexError/KeyError re-runs CPython's original.

        Covers an in-range list index, a negative index, an out-of-range read caught by the
        caller, a local list store, a dict hit, a missing key, and nested `a[i][j]`.
        """
        text = '''
def at(xs: list[int], i: int) -> int:
    return xs[i]

def last(xs: list[int]) -> int:
    return xs[-1]

def local(n: int) -> int:
    a = [10, 20, 30]
    return a[n]

def put(n: int) -> int:
    a = [1, 2, 3]
    a[1] = n
    return a[0] + a[1] + a[2]

def lookup(k: int) -> int:
    d = {1: 10, 2: 20}
    return d[k]

def nested(n: int, m: int) -> int:
    a = [[1, 2], [3, 4]]
    return a[n][m]

print('range', at([7, 8, 9], 0), at([7, 8, 9], 2), last([7, 8, 9]))
print('local', local(0), local(2), local(-1))
print('put', put(40), put(-5))
print('dict', lookup(1), lookup(2))
print('nested', nested(0, 0), nested(1, 1), nested(-1, -1))
for i in (3, -4, 99):
    try:
        print('index-exc', at([1, 2, 3], i))
    except IndexError as e:
        print('index-exc', type(e).__name__, str(e))
for k in (3, -1):
    try:
        print('key-exc', lookup(k))
    except KeyError as e:
        print('key-exc', type(e).__name__, str(e))
for n, m in ((2, 0), (0, 2), (-3, 0)):
    try:
        print('nested-exc', nested(n, m))
    except IndexError as e:
        print('nested-exc', type(e).__name__, str(e))
for empty in (lambda: at([], 0), lambda: last([])):
    try:
        empty()
    except IndexError as e:
        print('empty', type(e).__name__, str(e))
'''
        with tempfile.TemporaryDirectory(prefix='ail-cpython-hybrid-') as tmp:
            src, out, report = self.build(tmp, 'indexing', text)
            for name in ('at', 'last', 'local', 'put', 'lookup', 'nested'):
                self.assertIn(name, report['accelerated'], report)
            want = run([sys.executable, str(src)], tmp)
            got = run([str(out / 'indexing')], tmp)
            self.assertEqual(got.stdout, want.stdout)
            self.assertEqual(got.stderr, want.stderr)
            self.assertEqual(got.returncode, want.returncode)
            self.assertIn(b'index-exc IndexError list index out of range', got.stdout)
            self.assertIn(b'key-exc KeyError 3', got.stdout)
            self.assertIn(b'nested-exc IndexError list index out of range', got.stdout)

    def test_indexing_extension_really_loads(self):
        """obs1 defect: an indexing unit's extension failed to import (undefined trap symbol), the
        preamble swallowed the ImportError and build.json still claimed `first` was native."""
        text = 'def first(xs: list[int]) -> int:\n    return xs[0]\n'
        probe = '''
import sys
import _ail_first_fast as ext
import first as m
assert m._ail_hybrid_native is ext, m._ail_hybrid_native
assert NATIVE_CHECK, 'first is not the native entry'
print(m.first([7, 8]), ext.first([7, 8]))
try:
    m.first([])
except IndexError as e:
    print('IndexError', e)
'''
        with tempfile.TemporaryDirectory(prefix='ail-cpython-hybrid-') as tmp:
            src, out, report = self.build(tmp, 'first', text)
            self.assertEqual(report['accelerated'], ['first'], report)
            self.assertTrue((out / report['extension']).is_file(), report)
            check = 'ext._ail_is_native(m.first)'
            # cwd = out: `import first` must find the hybrid copy, not the source beside `tmp`
            got = run([sys.executable, '-B', '-c', probe.replace('NATIVE_CHECK', check)],
                      str(out), env=dict(os.environ, PYTHONPATH=str(out)))
            self.assertEqual(got.returncode, 0, got.stderr[-2000:])
            self.assertEqual(got.stdout, b'7 7\nIndexError list index out of range\n')

    def test_extension_that_does_not_import_is_not_claimed(self):
        """A `.so` that links but cannot load must not be listed as accelerated."""
        import ail_cpython_hybrid as hybrid
        text = 'def first(xs: list[int]) -> int:\n    return xs[0]\n\nprint(first([3]))\n'
        old = hybrid._trap_patch

        def broken(csrc, mangled):
            # reintroduce the obs1 defect: the trap flag loses external linkage
            return old(csrc, mangled).replace('\n__thread int %s__hybrid_trap' % mangled,
                                              '\nstatic __thread int %s__hybrid_trap' % mangled)
        hybrid._trap_patch = broken
        try:
            with tempfile.TemporaryDirectory(prefix='ail-cpython-hybrid-') as tmp:
                src = Path(tmp) / 'first.py'
                src.write_text(text, encoding='utf-8')
                report = hybrid.build(src, Path(tmp) / 'out')
                self.assertEqual(report['accelerated'], [], report)
                self.assertFalse(report['extension'], report)
                self.assertIn('did not import', report['rejected']['first'])
                self.assertFalse(list((Path(tmp) / 'out').glob('*.so')))
                saved = json.loads((Path(tmp) / 'out' / 'build.json').read_text())
                self.assertEqual(saved['accelerated'], [])
                got = run([str(Path(tmp) / 'out' / 'first')], tmp)
                self.assertEqual(got.stdout, b'3\n')
        finally:
            hybrid._trap_patch = old

    def test_rejected_reasons_are_named(self):
        """Every top-level function that stays in CPython carries a visible reason (wedge1 W0)."""
        text = '''
def keep(xs: list[int], i: int) -> int:
    return xs[i]

def power(a: float, b: float) -> float:
    return a ** b

def push(xs: list[int]) -> int:
    xs.append(9)
    return len(xs)

def nope(x: tuple) -> int:
    return len(x)
'''
        with tempfile.TemporaryDirectory(prefix='ail-cpython-hybrid-') as tmp:
            src, out, report = self.build(tmp, 'reasons', text)
            self.assertIn('keep', report['accelerated'])
            rejected = report['rejected']
            for name in ('power', 'push', 'nope'):
                self.assertIn(name, rejected)
                self.assertTrue(rejected[name], 'empty reason for %s' % name)

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

    def test_vectorcall_entry_matches_cpython(self):
        """obs2: the C entry is installed on the original function object.  Keywords, defaults,
        wrong arity, non-fitting arguments, `*args`/`**kw` call sites, map/partial, a replaced
        `__code__` or `__defaults__`, and introspection must all behave exactly as CPython."""
        text = '''
def add(a: int, b: int = 10) -> int:
    return a + b

def scale(x: float, k: float) -> float:
    return x * k

def flag(b: bool, n: int) -> int:
    return n + 1 if b else n - 1

def greet(s: str) -> str:
    return s + '!'
'''
        runner = '''
import functools, inspect, types
import vc as m
print(type(m.add) is types.FunctionType, m.add.__name__, m.add.__qualname__, m.add.__defaults__)
print(inspect.signature(m.add), m.add.__code__.co_varnames, m.add.__globals__ is vars(m))
print(m.add(1, 2), m.add(1), m.add(a=1, b=2), m.add(1, b=5), m.add(*(3, 4)), m.add(**{'a': 5}))
print(m.add(2**63 - 1, 1), m.add(-2**63, -1), m.add(2**70, 1), m.add(True, True), m.add(1.5, 2))
print(list(map(m.add, [1, 2], [3, 4])), functools.partial(m.add, b=1)(4))
for bad in ((), (1, 2, 3), ('a', 1), (None,)):
    try:
        print(m.add(*bad))
    except TypeError as e:
        print('TypeError', e)
try:
    m.add(1, c=2)
except TypeError as e:
    print('TypeError', e)
print(m.scale(1.5, 2.0), m.scale(3, 0.5), m.scale(float('nan'), 0.0), m.scale(1e308, 10.0))
print(m.flag(True, 1), m.flag(False, 1), m.flag(1, 1), m.greet('x'), m.greet('東京'))
try:
    m.greet(b'x')
except TypeError as e:
    print('TypeError', e)
m.add.__defaults__ = (100,)
print(m.add(1))
def other(a, b=0):
    return a - b
m.add.__code__ = other.__code__
print(m.add(1, 2), m.add(1))
'''
        probe = '''
import vc as m
nat = m._ail_hybrid_native
print([nat._ail_is_native(getattr(m, n)) for n in ('add', 'scale', 'flag', 'greet')])
'''
        with tempfile.TemporaryDirectory(prefix='ail-cpython-hybrid-') as tmp:
            src, out, report = self.build(tmp, 'vc', text)
            for name in ('add', 'scale', 'flag', 'greet'):
                self.assertIn(name, report['accelerated'])
            self.compare_imported(tmp, out, runner)
            got = run([sys.executable, '-B', '-c', probe], str(out),
                      env=dict(os.environ, PYTHONPATH=str(out)))
            self.assertEqual(got.stdout, b'[True, True, True, True]\n', got.stderr[-2000:])

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
