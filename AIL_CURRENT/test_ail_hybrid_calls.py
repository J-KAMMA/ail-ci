"""obs4 (`ail build --cpython`): module constants and calls between natives.

A native body may now read a module constant (`LIMIT = 3`) and call another selected native
(`total` calls `sq`, `depth` calls itself).  Both are names CPython looks up at run time, so the C
entry re-checks them before every call: a constant must still have the same exact type and value
in the module's globals, a callee must still be the def this unit compiled (its native entry, its
recorded code).  A dict watcher keeps the check to a flag test while nothing is rebound.  Every
entry also needs CPython's remaining recursion budget for the frames the call would push, and a
recursive unit's depth bound comes from that budget, so `RecursionError` happens exactly where
CPython raises it.  Every runner's output must equal CPython's byte for byte.
"""
import ast
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
sys.path.insert(0, str(ROOT))
CLI = str(ROOT / 'ail_chatgpt.py')
HAVE_CC = shutil.which(os.environ.get('PIPE_CC') or 'gcc') is not None
HAVE_HEADERS = (Path(sysconfig.get_paths().get('include', '/nonexistent')) / 'Python.h').is_file()
VECTORCALL = sys.version_info >= (3, 12)

import ail_cpython_hybrid as hybrid  # noqa: E402

CALLS = '''
LIMIT = 3
SCALE = 2.5
SEP = ","
ON = True


def under(n: int) -> bool:
    return n < LIMIT


def scaled(x: float) -> float:
    return x * SCALE


def seps(s: str) -> int:
    n = 0
    for ch in s:
        if ch == SEP:
            n += 1
    return n


def gated(n: int) -> int:
    if ON:
        return n + 1
    return n


def sq(x: int) -> int:
    return x * x


def total(n: int) -> int:
    acc = 0
    i = 0
    while i < n:
        acc += sq(i)
        i += 1
    return acc


def sqsum(a: int, b: int) -> int:
    return sq(a) + sq(b)


def is_start(ch: str) -> bool:
    return ch.isalpha() or ch == "_"


def count_starts(s: str) -> int:
    n = 0
    i = 0
    while i < len(s):
        if is_start(s[i]):
            n += 1
        i += 1
    return n


def digits(s: str) -> int:
    n = 0
    for ch in s:
        if ch.isdigit():
            n += 1
    return n


def depth(n: int) -> int:
    if n <= 0:
        return 0
    return depth(n - 1) + 1


def fib(n: int) -> int:
    if n < 2:
        return n
    return fib(n - 1) + fib(n - 2)


def is_even(n: int) -> bool:
    if n == 0:
        return True
    return is_odd(n - 1)


def is_odd(n: int) -> bool:
    if n == 0:
        return False
    return is_even(n - 1)


def add1(n: int) -> int:
    return n + 1
'''

RUNNER = '''
import sys
import calls as m


def show(label, f, *args):
    try:
        r = f(*args)
        print(label, type(r).__name__, repr(r))
    except Exception as e:
        print(label, 'raised', type(e).__name__)


show('under', m.under, 2)
show('scaled', m.scaled, 2.0)
show('seps', m.seps, 'a,b,,c')
show('gated', m.gated, 4)
show('total', m.total, 100)
show('sqsum', m.sqsum, 3, 4)
show('sqsum_ovf', m.sqsum, 2 ** 32, 3)
show('sqsum_big', m.sqsum, 2 ** 70, 3)
show('sqsum_bool', m.sqsum, True, 3)
show('starts', m.count_starts, 'ab _c 1d \\u6771')
show('digits', m.digits, 'a1b22')
show('fib', m.fib, 20)
show('even', m.is_even, 10)
m.LIMIT = 1
show('under_rebound', m.under, 2)
m.LIMIT = 2.5
show('under_float', m.under, 2)
m.LIMIT = 10 ** 30
show('under_big', m.under, 2)
del m.LIMIT
show('under_deleted', m.under, 2)
m.LIMIT = 3
show('under_restored', m.under, 2)
m.SEP = ';'
show('seps_rebound', m.seps, 'a;b,c')
m.SCALE = 2
show('scaled_int', m.scaled, 2.0)
vars(m)['ON'] = 0
show('gated_rebound', m.gated, 4)
real_sq = m.sq
m.sq = lambda x: 1
show('total_rebound', m.total, 10)
m.sq = real_sq
show('total_restored', m.total, 10)


def cube(x):
    return x * x * x


code = real_sq.__code__
real_sq.__code__ = cube.__code__
show('total_code', m.total, 10)
real_sq.__code__ = code
show('total_code_restored', m.total, 10)
old = m.depth
m.depth = lambda n: -100
show('depth_rebound', old, 5)
m.depth = old
show('depth_restored', old, 5)
sys.setrecursionlimit(120)
for n in range(100, 125):
    show('depth%d' % n, m.depth, n)


def deep(d, k):
    if k == 0:
        return m.add1(1)
    return deep(d, k - 1)


for k in range(100, 125):
    show('deep%d' % k, deep, {}, k)
sys.setrecursionlimit(1000)
for _ in range(2000):
    m.total(50)
    m.count_starts('ab_c')
    m.under(1)
print('loops-ok')
'''

EARLY = '''
def early(n: int) -> int:
    return n + LATE


try:
    print(early(1))
except NameError as e:
    print('NameError', e)
LATE = 5
print(early(1))
for _ in range(1000):
    early(2)
print(early(3))
'''

NATIVE = ('under', 'scaled', 'seps', 'sq', 'total', 'sqsum', 'is_start',
          'count_starts', 'digits', 'depth', 'fib', 'add1')
REFUSED = ('is_even', 'is_odd', 'gated')


def run(cmd, cwd=None, env=None):
    return subprocess.run(cmd, cwd=cwd, env=env, capture_output=True, timeout=600)


class Selection(unittest.TestCase):
    """Pure-AST pieces: no compiler needed."""

    def test_native_call_kinds_must_match_exactly(self):
        tree = ast.parse('def f(n):\n    return g(n > 0) + g(n) + g(n, 1) + g(x=n)\n')
        fn = tree.body[0]
        kinds = hybrid._Kinds(fn, [('n', 'int')], calls={'g': 'int'})
        calls = [c for c in ast.walk(fn) if isinstance(c, ast.Call)]
        natives = {'g': {'params': [('x', 'int')], 'ret': 'int'}}
        ok = {ast.unparse(c): hybrid._native_call_ok(c, natives, kinds) for c in calls}
        self.assertEqual(ok, {'g(n > 0)': False, 'g(n)': True, 'g(n, 1)': False,
                              'g(x=n)': False})
        self.assertEqual(kinds.kind(ast.parse('g(n) + 1', mode='eval').body), 'int')

    def test_constants_that_cannot_be_guarded(self):
        self.assertTrue(hybrid._guardable_constant(2 ** 63 - 1))
        self.assertFalse(hybrid._guardable_constant(2 ** 63))
        self.assertFalse(hybrid._guardable_constant(float('inf')))
        self.assertFalse(hybrid._guardable_constant('\ud800'))
        self.assertTrue(hybrid._guardable_constant('東'))
        # to_c refuses a bool module constant for the whole slice, so it is never added
        self.assertFalse(hybrid._guardable_constant(False))

    def test_link_refuses_mutual_recursion_and_missing_callees(self):
        tree = ast.parse('def a(n):\n    return b(n)\n\ndef b(n):\n    return a(n)\n\n'
                         'def c(n):\n    return d(n)\n\ndef d(n):\n    return n\n\n'
                         'def e(n):\n    return e(n) + f(n)\n\ndef f(n):\n    return f(n)\n')
        funcs = hybrid._top_level_functions(tree)
        chosen = {n: {'name': n} for n in ('a', 'b', 'c', 'e', 'f')}
        rejected = {}
        hybrid._link_natives(chosen, rejected, funcs, {}, {})
        self.assertEqual(sorted(chosen), ['f'])
        self.assertIn('mutual recursion', rejected['a'])
        self.assertIn('calls d', rejected['c'])
        self.assertIn('more than one recursive', rejected['e'])
        self.assertEqual(chosen['f']['callees'], ['f'])
        self.assertTrue(chosen['f']['recursive'])


@unittest.skipUnless(HAVE_CC and HAVE_HEADERS, 'needs a C compiler and the CPython headers')
class Runs(unittest.TestCase):

    def build(self, tmp, name, text):
        src = Path(tmp) / (name + '.py')
        src.write_text(text, encoding='utf-8')
        out = Path(tmp) / 'out'
        built = run([sys.executable, '-B', CLI, 'build', '--cpython', str(src), '-o', str(out)],
                    tmp, env=dict(os.environ, AIL_NO_CACHE='1'))
        self.assertEqual(built.returncode, 0, built.stderr[-3000:])
        return out, json.loads((out / 'build.json').read_text(encoding='utf-8'))

    def test_constants_and_calls_match_cpython(self):
        with tempfile.TemporaryDirectory(prefix='ail-hybrid-calls-') as tmp:
            out, report = self.build(tmp, 'calls', CALLS)
            for name in NATIVE:
                self.assertIn(name, report['accelerated'], report['rejected'].get(name))
            for name in REFUSED:
                self.assertNotIn(name, report['accelerated'])
            runner = Path(tmp) / 'runner.py'
            runner.write_text(RUNNER, encoding='utf-8')
            want = run([sys.executable, str(runner)], tmp, env=dict(os.environ, PYTHONPATH=tmp))
            got = run([sys.executable, str(runner)], tmp, env=dict(os.environ, PYTHONPATH=str(out)))
            self.assertEqual(got.stdout.decode(), want.stdout.decode(), got.stderr[-2000:])
            self.assertEqual(got.returncode, want.returncode)
            self.assertIn(b'loops-ok', got.stdout)
            # both sides of CPython's recursion limit are in the comparison
            self.assertIn(b'depth100 int 100', got.stdout)
            self.assertIn(b'depth124 raised RecursionError', got.stdout)
            self.assertIn(b'deep124 raised RecursionError', got.stdout)
            if VECTORCALL:
                probe = ('import calls as m\nnat = m._ail_hybrid_native\n'
                         'print([nat._ail_is_native(getattr(m, n)) for n in %r])\n' % (NATIVE,))
                got = run([sys.executable, '-B', '-c', probe], str(out),
                          env=dict(os.environ, PYTHONPATH=str(out)))
                self.assertEqual(got.stdout.strip(), repr([True] * len(NATIVE)).encode(),
                                 got.stderr[-2000:])

    def test_constant_read_before_assignment(self):
        with tempfile.TemporaryDirectory(prefix='ail-hybrid-early-') as tmp:
            out, report = self.build(tmp, 'early', EARLY)
            self.assertIn('early', report['accelerated'], report['rejected'].get('early'))
            want = run([sys.executable, str(Path(tmp) / 'early.py')], tmp)
            got = run([sys.executable, str(out / report['run_file'])], tmp)
            self.assertEqual(got.stdout, want.stdout, got.stderr[-2000:])
            self.assertEqual(got.returncode, want.returncode)
            self.assertIn(b'NameError', got.stdout)


if __name__ == '__main__':
    unittest.main()
