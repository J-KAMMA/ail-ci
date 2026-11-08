"""`ail build --cpython`: typed functions in a CPython extension, everything else in CPython.
The hybrid is explicit (the standalone build is untouched).  For a program whose functions are
typed-compilable, the generated extension is loaded and the Python module output must equal
CPython byte for byte, including the cases that must abandon the native call: an int outside
int64, an overflow inside the clone, a bool in an int/list[int] position, a missing argument
(default), None, and a mutated list parameter.  Functions whose body can trap in the typed runtime
(indexing, division by a variable, arbitrary calls, raise/try) stay in CPython; that includes
`divide` here; `first` indexes `xs[0]`, but an out-of-range index is detected and the Python
wrapper re-runs the original, so it is native too.  A division by a literal nonzero constant
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
            for name in ('add1', 'mul', 'isbig', 'half', 'join', 'total', 'first', 'dflt', 'echo'):
                self.assertIn(name, accelerated)
            self.assertNotIn('push', accelerated)          # a list parameter that is mutated
            self.assertNotIn('divide', accelerated)        # floor division can raise
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

    def test_rejected_reasons_are_named(self):
        """Every top-level function that stays in CPython carries a visible reason (wedge1 W0)."""
        text = '''
def keep(xs: list[int], i: int) -> int:
    return xs[i]

def divide(a: int, b: int) -> int:
    return a // b

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
            for name in ('divide', 'push', 'nope'):
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


    def test_methods_read_write_call_and_raise(self):
        """A plain class method goes native: `self.<field>` reads/writes cross the C wrapper.

        Covers an int field store (`add`), a `list[int]` field read through `len` (`Cols`), and a
        method that raises: `boom` stays in CPython so the caller sees CPython's own exception.
        A method that calls another method (`Counter.twice`, `Pair.both`) stays in CPython by
        name: `self.m(...)` keeps CPython's dynamic dispatch (subclass/instance/class-attribute
        overrides), which a direct kernel call would bypass.
        """
        text = '''
class Counter:
    def __init__(self, total: int) -> None:
        self.total = total
        self.count = 0

    def add(self, x: int) -> int:
        self.total = self.total + x
        self.count = self.count + 1
        return self.total

    def get(self) -> int:
        return self.total

    def twice(self) -> int:
        return self.get() + self.get()

    def boom(self) -> int:
        raise ValueError("boom")


class Pair:
    def __init__(self, a: int, b: int) -> None:
        self.a = a
        self.b = b

    def only_b(self) -> int:
        return self.b

    def both(self) -> int:
        return self.only_b() + self.a


class Cols:
    def __init__(self, xs: list[int]) -> None:
        self.xs = xs

    def size(self) -> int:
        return len(self.xs)


def main():
    c = Counter(0)
    print('add', c.add(5), c.add(7), c.get(), c.twice(), c.count, c.total)
    p = Pair(100, 7)
    print('pair', p.both(), p.only_b())
    print('cols', Cols([1, 2, 3]).size(), Cols([]).size(), Cols([-4]).size())
    try:
        c.boom()
    except ValueError as e:
        print('exc', type(e).__name__, e)

if __name__ == '__main__':
    main()
'''
        runner = '''
import methods_run as m
native = m._ail_hybrid_native
print('native', native is not None)
c = m.Counter(3)
print('direct', native.__ail_hybrid_method_Counter_add(c, 4), c.total, type(c.total).__name__)
print('get', native.__ail_hybrid_method_Counter_get(c))
'''
        with tempfile.TemporaryDirectory(prefix='ail-cpython-hybrid-') as tmp:
            src, out, report = self.build(tmp, 'methods', text)
            accelerated = set(report['accelerated'])
            for name in ('Counter.add', 'Counter.get', 'Pair.only_b', 'Cols.size'):
                self.assertIn(name, accelerated, report)
            for name in ('Counter.twice', 'Pair.both'):
                self.assertNotIn(name, accelerated, report)
                self.assertIn('another method', report['rejected'][name], report)
            self.assertIn('Counter.boom', report['rejected'])
            self.assertTrue(report['rejected']['Counter.boom'])
            want = run([sys.executable, str(src)], tmp)
            got = run([str(out / 'methods')], tmp)
            self.assertEqual(got.stdout, want.stdout)
            self.assertEqual(got.returncode, want.returncode)
            # The extension must really import: an undefined trap/overflow symbol would otherwise
            # leave every call on the Python fallback while still comparing equal.
            (Path(tmp) / 'run_native.py').write_text(runner, encoding='utf-8')
            direct = run([sys.executable, str(Path(tmp) / 'run_native.py')], tmp,
                         env=dict(os.environ, PYTHONPATH=str(out)))
            self.assertEqual(direct.returncode, 0, direct.stderr[-2000:])
            self.assertIn(b'native True', direct.stdout)
            self.assertIn(b'direct 7 7 int', direct.stdout)

    def test_method_dispatch_is_not_bypassed(self):
        """`self.m(...)` keeps CPython's dynamic dispatch under the hybrid.

        A method that calls another method is refused by name, so a subclass override, an
        instance attribute and a monkeypatched class attribute all change the answer exactly as in
        CPython.  A field-only method (`get`) is still lifted, and the refused caller falls back
        to its original Python body.
        """
        text = '''
class Base:
    def __init__(self, n: int) -> None:
        self.n = n

    def get(self) -> int:
        return self.n

    def twice(self) -> int:
        return self.get() * 2 + self.get()


class Sub(Base):
    def get(self) -> int:
        return self.n + 100


class Raiser(Base):
    def get(self) -> int:
        raise ValueError("override")


class Patch:
    def __init__(self, n: int) -> None:
        self.n = n

    def get(self) -> int:
        return self.n

    def twice(self) -> int:
        return self.get() * 2 + self.get()


print('base', Base(5).twice())
print('sub', Sub(5).twice())
try:
    print(Raiser(5).twice())
except ValueError as e:
    print('raiser', type(e).__name__, e)
inst = Base(5)
inst.get = lambda: 99
print('inst', inst.twice())
patched = Patch(3)
Patch.get = lambda self: 7 + self.n
print('patch', patched.twice())
'''
        with tempfile.TemporaryDirectory(prefix='ail-cpython-hybrid-') as tmp:
            src, out, report = self.build(tmp, 'dispatch', text)
            accelerated = set(report['accelerated'])
            self.assertIn('Base.get', accelerated, report)
            self.assertIn('Patch.get', accelerated, report)
            for name in ('Base.twice', 'Patch.twice'):
                self.assertNotIn(name, accelerated, report)
                self.assertIn('another method', report['rejected'][name], report)
            want = run([sys.executable, str(src)], tmp)
            got = run([str(out / 'dispatch')], tmp)
            self.assertEqual(got.stdout, want.stdout)
            self.assertEqual(got.returncode, want.returncode)
            self.assertIn(b'base 15', got.stdout)
            self.assertIn(b'sub 315', got.stdout)
            self.assertIn(b'raiser ValueError override', got.stdout)
            self.assertIn(b'inst 297', got.stdout)
            self.assertIn(b'patch 30', got.stdout)

    def test_subclass_field_override_prevents_batching(self):
        """A subclass that rebinds a field name keeps the parent's methods in CPython.

        The wrapper reads each field once and re-executes the body, while CPython evaluates every
        `self.n` occurrence.  A property (or other class-body binding of `n`) makes each access
        observable, so the parent's method must not be lifted.
        """
        text = '''
class Base:
    def __init__(self, n: int) -> None:
        self.n = n

    def twice(self) -> int:
        return self.n + self.n


class Sub(Base):
    def __init__(self) -> None:
        self.i = 5
        self.calls = 0

    @property
    def n(self):
        self.calls += 1
        return self.i + self.calls


class Plain(Base):
    def __init__(self, n: int) -> None:
        self.n = n


s = Sub()
print('sub', s.twice(), s.calls)
print('base', Base(3).twice())
print('plain', Plain(4).twice())
'''
        with tempfile.TemporaryDirectory(prefix='ail-cpython-hybrid-') as tmp:
            src, out, report = self.build(tmp, 'fieldbatch', text)
            self.assertNotIn('Base.twice', report['accelerated'], report)
            self.assertIn('subclass', report['rejected']['Base.twice'], report)
            want = run([sys.executable, str(src)], tmp)
            got = run([str(out / 'fieldbatch')], tmp)
            self.assertEqual(got.stdout, want.stdout)
            self.assertEqual(got.returncode, want.returncode)
            self.assertIn(b'sub 13 2', got.stdout)

    def test_return_kinds_agree_or_refuse(self):
        """A return kind is inferred from every `return` when they all agree; mixed stays CPython.

        `and`/`or` of two bools is a bool (the old inference left it unresolved); `0 or a`
        evaluates to an int; a function with an int return and a str return is refused by name.
        """
        text = '''
def agree_bool(a: int, b: int) -> bool:
    return a > 0 and b > 0

def agree_int(a: int) -> int:
    return 0 or a

def mixed(flag: bool) -> int:
    if flag:
        return 1
    return "x"

def both_values(a: int, b: int) -> int:
    return a or b

print('bool', agree_bool(1, 2), agree_bool(1, 0), agree_bool(-1, 2))
print('int', agree_int(0), agree_int(7), agree_int(-3))
print('both', both_values(0, 5), both_values(3, 5), both_values(-1, -2))
print('mixed', mixed(True))
try:
    print('mixed', mixed(False))
except Exception as e:
    print('mixed-exc', type(e).__name__)
'''
        with tempfile.TemporaryDirectory(prefix='ail-cpython-hybrid-') as tmp:
            src, out, report = self.build(tmp, 'returns', text)
            for name in ('agree_bool', 'agree_int', 'both_values'):
                self.assertIn(name, report['accelerated'], report)
            self.assertIn('mixed', report['rejected'])
            self.assertIn('unresolved-return', report['rejected']['mixed'])
            want = run([sys.executable, str(src)], tmp)
            got = run([str(out / 'returns')], tmp)
            self.assertEqual(got.stdout, want.stdout)
            self.assertEqual(got.returncode, want.returncode)

    def test_annotated_and_unannotated_parameters(self):
        """Parameter kinds come from annotations and from the module's own call sites.

        An unannotated top-level parameter with consistent int call sites resolves; conflicting
        call sites (int and str) leave it unresolved and the function in CPython.  A class whose
        `__init__` and one method parameter are unannotated resolves them from `Q(1)` and from the
        `self.plus(k)` call site inside the class.  `Q.step` itself stays in CPython because it
        calls another method, but that call site still seeds `Q.plus`'s parameter.
        """
        text = '''
class Q:
    def __init__(self, n):
        self.n = n

    def step(self, k: int) -> int:
        return self.plus(k)

    def plus(self, k):
        return self.n + k


def annotated(n: int, s: str) -> str:
    return s + str(n)


def unannotated(n):
    return n + 1


def agreement(a, b):
    return a * b


def disagreement(x):
    return x


print('annotated', annotated(3, 'n'), annotated(-4, 'n'))
print('unannotated', unannotated(1), unannotated(2))
print('agreement', agreement(2, 3), agreement(-2, 5))
print('disagreement', disagreement(1), disagreement('a'))
q = Q(1)
print('q', q.step(2), q.plus(10))
'''
        with tempfile.TemporaryDirectory(prefix='ail-cpython-hybrid-') as tmp:
            src, out, report = self.build(tmp, 'params', text)
            for name in ('annotated', 'unannotated', 'agreement', 'Q.plus'):
                self.assertIn(name, report['accelerated'], report)
            self.assertNotIn('Q.step', report['accelerated'], report)
            self.assertIn('another method', report['rejected']['Q.step'], report)
            self.assertIn('disagreement', report['rejected'])
            want = run([sys.executable, str(src)], tmp)
            got = run([str(out / 'params')], tmp)
            self.assertEqual(got.stdout, want.stdout)
            self.assertEqual(got.returncode, want.returncode)


if __name__ == '__main__':
    unittest.main()
