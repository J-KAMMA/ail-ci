"""obs3 (`ail build --cpython`): list results, `list[float]` parameters passed as `ail_flist`, and
the exact-type proofs behind them.

A hybrid function that returns `list[int]`/`list[float]` hands back a new CPython list built from
the clone's buffer; that is only indistinguishable from CPython when the list is a fresh local the
function built itself and every element is an exact `int` (never a bool) or an exact `float`.  The
proof lives in `_list_return_proof`; anything it cannot prove stays in CPython.  A long result
(more than the wrapper's stack buffer) goes through the unit's spill slot, two list-returning
units in one extension must link, an int64 overflow or an index/key stop falls back to CPython,
and a float result whose int arithmetic overflows falls back instead of stopping the process.
Every runner's output must equal CPython's byte for byte.
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

import ail_cpython_hybrid as hybrid  # noqa: E402

LISTS = '''
def squares(n: int) -> list[int]:
    out = []
    i = 0
    while i < n:
        out.append(i * i)
        i += 1
    return out


def scaled(xs: list[float], k: float) -> list[float]:
    out = []
    for x in xs:
        out.append(x * k)
    return out


def grid(n: int, v: int) -> list[int]:
    out = [0] * n
    i = 0
    while i < n:
        out[i] = v * i
        i += 1
    if n > 0:
        out[-1] = 7
    return out


def bucket(keys: list[int], n: int) -> list[int]:
    out = [0] * n
    for k in keys:
        out[k] += 1
    return out


def flags(xs: list[int]) -> list[int]:
    out = []
    for x in xs:
        out.append(x > 0)
    return out


def mixed(n: int) -> list[float]:
    out = [0] * n
    i = 0
    while i < n:
        out[i] = i * 0.5
        i += 1
    return out


def alias_ret(xs: list[int]) -> list[int]:
    out = xs
    return out


def dotf(a: list[float], b: list[float]) -> float:
    acc = 0.0
    i = 0
    n = len(a)
    while i < n:
        acc += a[i] * b[i]
        i += 1
    return acc


def count_len(xs: list[int]) -> int:
    n = len(xs)
    total = 0
    i = 0
    while i < n:
        total += xs[i]
        i += 1
    return total


def fmul(n: int) -> float:
    return n * n * 0.5
'''

RUNNER = '''
import lists as m


def show(label, f, *args):
    try:
        r = f(*args)
        print(label, type(r).__name__, repr(r)[:400])
    except Exception as e:
        print(label, 'raised', type(e).__name__, e)


show('sq0', m.squares, 0)
show('sq5', m.squares, 5)
show('sq64', lambda: m.squares(64)[-2:])
show('sq65', lambda: m.squares(65)[-2:])
show('sqbig', lambda: sum(m.squares(200000)))
show('sc', m.scaled, [0.1, 0.2, 1e300, -0.0, float('inf')], 3.0)
show('scbig', lambda: m.scaled([0.1] * 1000, 1e308)[-2:])
show('scint', m.scaled, [1, 2.5], 2.0)
show('grid', m.grid, 5, 3)
show('gridneg', m.grid, -3, 3)
show('gridovf', m.grid, 3, 2 ** 62)
show('bucket', m.bucket, [0, 1, 1, 2, -1, -3], 3)
show('bucketerr', m.bucket, [0, 5], 3)
show('flags', m.flags, [1, -1, 0])
show('mixed', m.mixed, 4)
show('dotf', m.dotf, [1.5, 2.5], [2.0, 4.0])
show('dotfint', m.dotf, [1, 2.5], [2.0, 4.0])
show('dotfshort', m.dotf, [1.5, 2.5], [2.0])
show('cl', m.count_len, [1, 2, 3])
show('clbig', m.count_len, [2 ** 62, 2 ** 62])
show('fmul', m.fmul, 3)
show('fmulbig', m.fmul, 2 ** 40)
a = m.squares(3)
b = m.squares(3)
a.append(99)
show('fresh', lambda: (a, b, a is b))
x = [1, 2]
show('alias', lambda: m.alias_ret(x) is x)
for _ in range(3000):
    m.squares(100)
    m.scaled([0.5] * 100, 2.0)
    m.grid(70, 3)
print('loops-ok')
'''

NATIVE = ('squares', 'scaled', 'grid', 'bucket', 'dotf', 'count_len', 'fmul')
REFUSED = ('flags', 'mixed', 'alias_ret')


def run(cmd, cwd=None, env=None):
    return subprocess.run(cmd, cwd=cwd, env=env, capture_output=True, timeout=600)


def fn(text):
    return ast.parse(text).body[0]


class Proofs(unittest.TestCase):
    """`_list_return_proof` and `_return_kinds` on plain ASTs (no compiler needed)."""

    def proof(self, text, params):
        return hybrid._list_return_proof(fn(text), params)

    def test_fresh_int_and_float_lists(self):
        self.assertEqual(self.proof('def f(n):\n    out = []\n    out.append(n + 1)\n'
                                    '    return out\n', [('n', 'int')]), ('list[int]', 'out'))
        self.assertEqual(self.proof('def f(xs, k):\n    out = []\n    for x in xs:\n'
                                    '        out.append(x * k)\n    return out\n',
                                    [('xs', 'list[float]'), ('k', 'float')]),
                         ('list[float]', 'out'))
        self.assertEqual(self.proof('def f(k, n):\n    out = [0] * n\n    for i in k:\n'
                                    '        out[i] += 1\n    return out\n',
                                    [('k', 'list[int]'), ('n', 'int')]), ('list[int]', 'out'))
        self.assertEqual(self.proof('def f(n):\n    acc = 0\n    out = []\n    i = 0\n'
                                    '    while i < n:\n        acc += i\n        out.append(acc)\n'
                                    '        i += 1\n    return out\n', [('n', 'int')]),
                         ('list[int]', 'out'))

    def test_refusals(self):
        cases = [
            # a bool element is True/False in CPython, 1/0 in an int64 buffer
            ('def f(xs):\n    out = []\n    for x in xs:\n        out.append(x > 0)\n'
             '    return out\n', [('xs', 'list[int]')]),
            # [0] * n holds ints; the stores hold floats: a mixed list
            ('def f(n):\n    out = [0] * n\n    out[0] = 0.5\n    return out\n', [('n', 'int')]),
            # x is an int on one path and a float on another
            ('def f(n):\n    x = 0\n    if n:\n        x = 1.5\n    out = [x]\n    return out\n',
             [('n', 'int')]),
            # the parameter itself (identity must be preserved)
            ('def f(xs):\n    return xs\n', [('xs', 'list[int]')]),
            ('def f(xs):\n    out = xs\n    return out\n', [('xs', 'list[int]')]),
            # the list escapes before the return
            ('def f(n):\n    out = []\n    keep = out\n    out.append(n)\n    return out\n',
             [('n', 'int')]),
            ('def f(n):\n    out = []\n    g(out)\n    return out\n', [('n', 'int')]),
            # a path falls off the end (None)
            ('def f(n):\n    out = [n]\n    if n:\n        return out\n', [('n', 'int')]),
            # an empty list has no element type
            ('def f(n):\n    out = []\n    return out\n', [('n', 'int')]),
            # `sum` of a float list is the int 0 when empty
            ('def f(xs):\n    out = [sum(xs)]\n    return out\n', [('xs', 'list[float]')]),
            # a nested function sees the list
            ('def f(n):\n    out = []\n    h = lambda: out\n    out.append(n)\n    return out\n',
             [('n', 'int')]),
        ]
        for text, params in cases:
            kind, why = self.proof(text, params)
            self.assertIsNone(kind, text)
            self.assertTrue(why, text)

    def test_return_kinds(self):
        self.assertEqual(hybrid._return_kinds(fn('def f(c):\n    return c.isalpha() or c == "_"\n'),
                                              [('c', 'str')]), ['bool'])
        self.assertEqual(hybrid._return_kinds(fn('def f(a, b):\n    return a > 0 and b\n'),
                                              [('a', 'int'), ('b', 'int')]), [None])
        self.assertEqual(hybrid._return_kinds(fn('def f(a, b):\n    return a and b\n'),
                                              [('a', 'int'), ('b', 'int')]), ['int'])
        self.assertEqual(hybrid._return_kinds(
            fn('def f(s):\n    n = 0\n    for ch in s:\n        n += 1\n'
               '    return n > 0 and n <= 9\n'), [('s', 'str')]), ['bool'])
        self.assertEqual(hybrid._return_kinds(fn('def f(n):\n    if n:\n        return True\n'),
                                              [('n', 'int')]), ['bool', 'none'])

    def test_len_is_not_a_mutation(self):
        f = fn('def f(xs):\n    n = len(xs)\n    return n\n')
        self.assertFalse(hybrid._list_param_mutated(f, {'xs'}))
        self.assertTrue(hybrid._list_param_mutated(f, {'xs'}, shadowed={'len'}))
        g = fn('def f(xs):\n    other(xs)\n    return 0\n')
        self.assertTrue(hybrid._list_param_mutated(g, {'xs'}))

    def test_unit_abi(self):
        csrc = ('double f__typed(ail_flist v_a, const double *v_b, int64_t v_b_len, '
                'double v_w) {\n')
        self.assertEqual(hybrid._unit_abi(csrc, 'f__typed', [('a', 'list[float]'),
                                                             ('b', 'list[float]'),
                                                             ('w', 'float')], 'float'),
                         {'a': 'flist', 'b': 'arr', 'w': 'scalar'})
        csrc = 'int64_t g__typed(int64_t v_n, int64_t *_out, int64_t _cap) {\n'
        self.assertEqual(hybrid._unit_abi(csrc, 'g__typed', [('n', 'int')], 'list[int]'),
                         {'n': 'scalar'})
        self.assertIsNone(hybrid._unit_abi(csrc, 'g__typed', [('n', 'int')], 'list[float]'))
        self.assertIsNone(hybrid._unit_abi(csrc, 'g__typed', [('n', 'int')], 'int'))

    def test_list_result_keeps_the_gil(self):
        items = [{'name': 'mk', 'mangled': 'mk__typed', 'params': [('n', 'int')],
                  'ret': 'list[int]', 'is_bool_ret': False, 'abi': {'n': 'scalar'},
                  'trap': True}]
        src = hybrid._wrapper_source('m', items)
        self.assertNotIn('Py_BEGIN_ALLOW_THREADS', src[src.index('ail_core_mk(PyObject *const *o) {'):])
        self.assertIn('mk__typed__hybrid_spill(&lp)', src)

    def test_loop_free_body_keeps_the_gil(self):
        items = [{'name': 'short', 'mangled': 'short__typed', 'params': [('s', 'str')],
                  'ret': 'bool', 'is_bool_ret': True, 'loops': False},
                 {'name': 'longer', 'mangled': 'longer__typed', 'params': [('n', 'int')],
                  'ret': 'int', 'is_bool_ret': False, 'loops': True}]
        src = hybrid._wrapper_source('m', items)
        short = src[src.index('ail_core_short(PyObject *const *o) {'):src.index('ail_w_longer')]
        longer = src[src.index('ail_core_longer(PyObject *const *o) {'):]
        self.assertNotIn('Py_BEGIN_ALLOW_THREADS', short)
        self.assertIn('Py_BEGIN_ALLOW_THREADS', longer)


@unittest.skipUnless(HAVE_CC and HAVE_HEADERS, 'needs a C compiler and the CPython headers')
class ListResults(unittest.TestCase):
    def test_list_results_match_cpython(self):
        with tempfile.TemporaryDirectory(prefix='ail-hybrid-lists-') as tmp:
            src = Path(tmp) / 'lists.py'
            src.write_text(LISTS, encoding='utf-8')
            out = Path(tmp) / 'out'
            built = run([sys.executable, '-B', CLI, 'build', '--cpython', str(src), '-o', str(out)],
                        tmp, env=dict(os.environ, AIL_NO_CACHE='1'))
            self.assertEqual(built.returncode, 0, built.stderr[-3000:])
            report = json.loads((out / 'build.json').read_text(encoding='utf-8'))
            self.assertTrue(report['extension'], report)
            for name in NATIVE:
                self.assertIn(name, report['accelerated'], report['rejected'].get(name))
            for name in REFUSED:
                self.assertNotIn(name, report['accelerated'])
            runner = Path(tmp) / 'runner.py'
            runner.write_text(RUNNER, encoding='utf-8')
            want = run([sys.executable, str(runner)], tmp, env=dict(os.environ, PYTHONPATH=tmp))
            got = run([sys.executable, str(runner)], tmp, env=dict(os.environ, PYTHONPATH=str(out)))
            self.assertEqual(got.stdout, want.stdout, got.stderr[-2000:])
            self.assertEqual(got.returncode, want.returncode)
            self.assertIn(b'loops-ok', got.stdout)
            probe = ('import lists as m\nnat = m._ail_hybrid_native\n'
                     'print([nat._ail_is_native(getattr(m, n)) for n in %r])\n' % (NATIVE,))
            got = run([sys.executable, '-B', '-c', probe], str(out),
                      env=dict(os.environ, PYTHONPATH=str(out)))
            self.assertEqual(got.stdout.strip(), repr([True] * len(NATIVE)).encode(),
                             got.stderr[-2000:])


BOOLS = '''
LIMIT = 9


def is_ident_start(ch: str) -> bool:
    return ch.isalpha() or ch == "_"


def in_range(n: int) -> bool:
    return n > 0 and n <= 9


def in_limit(n: int) -> bool:
    return n > 0 and n <= LIMIT


def either(a: int, b: int) -> int:
    return a and b


def lies(a: int, b: int) -> bool:
    return a and b


def count(s: str) -> int:
    n = 0
    for ch in s:
        if is_ident_start(ch):
            n += 1
    return n
'''

BOOL_RUNNER = '''
import bools as m
for args in (('a',), ('_',), ('1',), ('',), ('\\u6771',)):
    print('start', args, repr(m.is_ident_start(*args)))
for n in (-1, 0, 1, 9, 10, 2 ** 70, True):
    print('range', n, repr(m.in_range(n)), repr(m.in_limit(n)))
for a, b in ((0, 5), (3, 5), (3, 0), (2 ** 70, 1), (True, 2)):
    print('either', repr(m.either(a, b)), 'lies', repr(m.lies(a, b)))
print('count', m.count('ab_1 c\\u67719'))
try:
    m.is_ident_start(5)
except AttributeError as e:
    print('AttributeError', e)
'''


@unittest.skipUnless(HAVE_CC and HAVE_HEADERS, 'needs a C compiler and the CPython headers')
class SeededReturns(unittest.TestCase):
    """Task 2: a `-> bool` (or other scalar) annotation seeds the result kind only when the body
    proves every return value has that exact type; `return a and b` with int operands returns an
    int whatever the annotation says, so `lies` stays in CPython."""

    def test_bool_results_match_cpython(self):
        with tempfile.TemporaryDirectory(prefix='ail-hybrid-bools-') as tmp:
            src = Path(tmp) / 'bools.py'
            src.write_text(BOOLS, encoding='utf-8')
            out = Path(tmp) / 'out'
            built = run([sys.executable, '-B', CLI, 'build', '--cpython', str(src), '-o', str(out)],
                        tmp, env=dict(os.environ, AIL_NO_CACHE='1'))
            self.assertEqual(built.returncode, 0, built.stderr[-3000:])
            report = json.loads((out / 'build.json').read_text(encoding='utf-8'))
            # `count` calls a user function, which the body gate still refuses, and `in_limit`
            # reads a module constant, which `to_c` refuses in a defs-only slice; both are here
            # for the output comparison.
            for name in ('is_ident_start', 'in_range', 'either'):
                self.assertIn(name, report['accelerated'], report['rejected'].get(name))
            self.assertNotIn('lies', report['accelerated'])
            runner = Path(tmp) / 'runner.py'
            runner.write_text(BOOL_RUNNER, encoding='utf-8')
            want = run([sys.executable, str(runner)], tmp, env=dict(os.environ, PYTHONPATH=tmp))
            got = run([sys.executable, str(runner)], tmp, env=dict(os.environ, PYTHONPATH=str(out)))
            self.assertEqual(got.stdout, want.stdout, got.stderr[-2000:])
            self.assertEqual(got.returncode, want.returncode)
            probe = ('import bools as m\nnat = m._ail_hybrid_native\n'
                     'print([nat._ail_is_native(getattr(m, n)) for n in '
                     '("is_ident_start", "in_range", "either", "lies")])\n')
            got = run([sys.executable, '-B', '-c', probe], str(out),
                      env=dict(os.environ, PYTHONPATH=str(out)))
            self.assertEqual(got.stdout.strip(), b'[True, True, True, False]',
                             got.stderr[-2000:])


if __name__ == '__main__':
    unittest.main()
