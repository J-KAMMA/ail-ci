"""Nested expressions compile in roughly linear time; `except E as k` unbinds k; handler re-raise; free-variable text.

* compile time: a nested arithmetic expression, `f(f(...))`, a nested list literal, a nested dict literal, a nested
  conditional expression and nested comprehensions used to take exponential time (_etype and the shape queries re-walked
  every subtree).  Depth 24 of each shape must build (compile + gcc) in a few seconds; the old compiler did not finish
  depth 12 of the list literal in 120 s.
* DIFFERENCES C146: the general path did not delete `k` at the end of `except E as k`.
* DIFFERENCES C147: a handler that re-raises (`raise`, `raise e`, `raise X from e`), with or without `finally`,
  must be caught by the caller's handler in mixed mode; the free-variable error reads CPython's text.
Each program is built by the default build and with --general-only and must print what CPython prints.
"""
import os
import subprocess
import sys
import tempfile
import time
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / 'python' / 'pkg-v12'))

from test_ail_bugs7 import _cpython, build          # noqa: E402

HERE = Path(__file__).resolve().parent
DEPTH = 24
LIMIT = 15.0      # seconds, compile plus gcc, per shape at depth 24 (measured: 1-4 s; exponential: minutes)


def nested(shape, d):
    if shape == 'arith':
        e = 'x'
        for i in range(d):
            e = '(%s + %d * (x - %d))' % (e, i + 1, i)
        return 'def main():\n    x = 3\n    print(%s)\nmain()\n' % e
    if shape == 'call':
        e = 'x'
        for i in range(d):
            e = 'f(%s)' % e
        return 'def f(a: int) -> int:\n    return a + 1\ndef main():\n    x = 3\n    print(%s)\nmain()\n' % e
    if shape == 'list':
        e = '1'
        for i in range(d):
            e = '[%s, %d]' % (e, i)
        return 'def main():\n    print(%s)\nmain()\n' % e
    if shape == 'dict':
        e = '1'
        for i in range(d):
            e = '{%d: %s}' % (i, e)
        return 'def main():\n    print(%s)\nmain()\n' % e
    if shape == 'cond':
        e = 'x'
        for i in range(d):
            e = '(%s if x > %d else %d)' % (e, i, i)
        return 'def main():\n    x = 3\n    print(%s)\nmain()\n' % e
    e = 'i0'                                  # comp: CPython's parser itself fails beyond ~20 levels
    for i in range(d):
        e = '[%s for j%d in range(1)]' % (e, i)
    return 'def main():\n    i0 = 1\n    print(%s)\nmain()\n' % e


def run(directory, name, text, general):
    """The driver (ail_chatgpt compile), as a user builds: default build, or the general path forced."""
    want = _cpython(directory, name, text, '')
    src = Path(directory) / ('%s_%d.py' % (name, general))
    src.write_text(text, encoding='utf-8')
    exe = Path(directory) / ('exe_%s_%d' % (name, general))
    env = dict(os.environ, AIL_NO_CACHE='1', AIL_QUIET_FALLBACK='1')
    env.pop('AIL_UNIFIED_FORCE', None)
    if general:
        env['AIL_UNIFIED_FORCE'] = '1'
    built = subprocess.run([sys.executable, '-B', str(HERE / 'ail_chatgpt.py'), 'compile', str(src), '--syntax',
                            'python', '-o', str(exe)], cwd=directory, capture_output=True, text=True, timeout=900, env=env)
    if built.returncode:
        return want, ('BUILD FAILED', built.stderr[-800:])
    done = subprocess.run([str(exe)], capture_output=True, timeout=60, cwd=directory)
    return want, (done.stdout.replace(b'\r\n', b'\n'), done.returncode)


class Nest(unittest.TestCase):
    def check(self, name, text):
        with tempfile.TemporaryDirectory() as d:
            for general in (False, True):
                want, got = run(d, name, text, general)
                self.assertEqual(got, want, '%s general=%s' % (name, general))

    def test_depth_24_compiles_in_a_few_seconds(self):
        def one(shape):
            d = DEPTH if shape != 'comp' else 12
            with tempfile.TemporaryDirectory() as td:
                text = nested(shape, d)
                t0 = time.time()
                exe, built = build(td, shape, text, '1', False)
                took = time.time() - t0
                self.assertEqual(built.returncode, 0, built.stderr[-800:])
                done = subprocess.run([str(exe)], capture_output=True, timeout=60)
                want = _cpython(td, shape, text, '')
                self.assertEqual((done.stdout.replace(b'\r\n', b'\n'), done.returncode), want, shape)
                return shape, took
        with ThreadPoolExecutor(2) as ex:
            for shape, took in ex.map(one, ['arith', 'call', 'list', 'dict', 'cond', 'comp']):
                self.assertLess(took, LIMIT, '%s at depth: %.1f s' % (shape, took))

    def test_except_as_unbinds(self):
        self.check('exas', '''
def rd(fn):
    try:
        return fn()
    except NameError as q:
        return type(q).__name__
def a(n):
    try:
        1 // n
    except ZeroDivisionError as k:
        pass
    return k
def b(n):
    k = 5
    try:
        1 // n
    except ZeroDivisionError as k:
        pass
    return k
def c(n):
    out = 0
    for i in range(n):
        try:
            1 // (i - 1)
        except ZeroDivisionError as k:
            out += 1
            continue
    return out, k
def d(n):
    for i in range(n):
        try:
            1 // 0
        except ZeroDivisionError as k:
            break
    return k
def e2(n):
    try:
        try:
            1 // n
        except ZeroDivisionError as k:
            raise ValueError("inner")
    except ValueError as k:
        pass
    return k
def g(n):
    try:
        1 // n
    except ZeroDivisionError as k:
        pass
    try:
        int("z")
    except ValueError as k:
        pass
    return k
def gen(n):
    try:
        1 // n
    except ZeroDivisionError as k:
        yield 1
    yield k
def h(n):
    try:
        try:
            1 // n
        except ZeroDivisionError as k:
            raise
    except ZeroDivisionError:
        pass
    return k
print(rd(lambda: a(0)))
print(rd(lambda: b(0)))
print(rd(lambda: c(3)))
print(rd(lambda: d(2)))
print(rd(lambda: e2(0)))
print(rd(lambda: g(0)))
print(rd(lambda: list(gen(0))))
print(rd(lambda: h(0)))
try:
    1 // 0
except ZeroDivisionError as mk:
    pass
print(rd(lambda: mk))
''')

    def test_handler_reraise_reaches_caller(self):
        parts = []
        n = 0
        for form in ('raise', 'raise e', 'raise RuntimeError("x") from e'):
            for fin in (False, True):
                for lvl in (1, 2):
                    n += 1
                    fn = 'f%d' % n
                    f = '    finally:\n        pass\n' if fin else ''
                    parts.append('def %s_in(n: int) -> int:\n    try:\n        x = 1 // n\n'
                                 '    except ZeroDivisionError as e:\n        %s\n%s    return x\n' % (fn, form, f))
                    call = fn + '_in'
                    if lvl == 2:
                        parts.append('def %s_mid(n: int) -> int:\n    try:\n        return %s_in(n)\n'
                                     '    except ZeroDivisionError as e:\n        %s\n%s' % (fn, fn, form, f))
                        call = fn + '_mid'
                    parts.append('def %s(n: int) -> int:\n    try:\n        return %s(n)\n'
                                 '    except ZeroDivisionError as e:\n        print("%s caught", e)\n        return -1\n'
                                 '    except RuntimeError as e:\n        print("%s runtime", e)\n        return -2\n'
                                 'print(%s(0), %s(5))\n' % (fn, call, fn, fn, fn, fn))
        self.check('reraise', '\n'.join(parts))
        self.check('reraise_boxed', '''
def inner(n):
    try:
        x = 1 / n
    except ZeroDivisionError:
        raise
    finally:
        pass
    return x
def outer(d, k):
    try:
        return d[k] + inner(d[k])
    except ZeroDivisionError:
        return "zde " + str(k)
d = {"a": 0, "b": 2}
print(outer(d, "a"), outer(d, "b"))
''')

    def test_free_variable_text(self):
        self.check('freevar', '''
def h2():
    y = 1
    def inner():
        nonlocal y
        y += 1
        return y
    del y
    try: inner()
    except NameError as e: print(type(e).__name__, e)
h2()
def h1():
    def inner():
        return y
    try: inner()
    except NameError as e: print(type(e).__name__, e)
    y = 2
    print(inner())
h1()
def h4():
    def inner():
        return z
    try: inner()
    except NameError as e: print(e)
    z = 1
    del z
    try: inner()
    except NameError as e: print(e)
h4()
''')


if __name__ == '__main__':
    unittest.main()
