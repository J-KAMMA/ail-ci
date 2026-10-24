"""Differential recursion probes: recursive classmethods and common recursive shapes."""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent

CLASSMETHOD_RECEIVER = r'''class C:
    @classmethod
    def same(cls, n: int) -> bool:
        if n <= 0:
            return cls is C
        return cls.same(n - 1)

    @classmethod
    def kind(cls, n: int) -> str:
        if n <= 0:
            return cls.__class__.__name__
        return cls.kind(n - 1)


class D(C):
    pass


c: C = C()
d: D = D()
print(C.same(0), C.same(1), C.same(4))
print(c.same(0), c.same(3), d.same(0), d.same(3))
print(D.same(0), D.same(3))
print(C.kind(0), C.kind(1), C.kind(4))
print(D.kind(0), D.kind(2))
'''

CLASSMETHOD_CALLS = r'''class C:
    @classmethod
    def a(cls, n: int) -> bool:
        if n <= 0:
            return cls is C
        return cls.b(n)

    @classmethod
    def b(cls, n: int) -> bool:
        return cls.a(n - 1)

    @classmethod
    def total(cls, n: int, acc: int) -> int:
        if n <= 0:
            return acc
        return cls.total(n - 1, acc + n)


print(C.a(0), C.a(1), C.a(4))
print(C.total(0, 5), C.total(4, 5), C().total(3, -2))
'''

RECURSION_SHAPES = r'''def fact(n: int) -> int:
    if n <= 1:
        return 1
    return n * fact(n - 1)


def even(n: int) -> bool:
    if n <= 0:
        return True
    return odd(n - 1)


def odd(n: int) -> bool:
    if n <= 0:
        return False
    return even(n - 1)


MEMO: dict[int, int] = {}


def fib(n: int) -> int:
    if n <= 1:
        return n
    if n in MEMO:
        return MEMO[n]
    r: int = fib(n - 1) + fib(n - 2)
    MEMO[n] = r
    return r


def total(xs: list[int], i: int) -> int:
    if i >= len(xs):
        return 0
    return xs[i] + total(xs, i + 1)


print(fact(0), fact(1), fact(10))
print(even(0), even(1), even(10), odd(7))
print(fib(0), fib(1), fib(10), fib(40), len(MEMO))
print(total([], 0), total([1, 2, 3], 0), total([-5], 0))
'''


def _cpython(directory, name, text):
    src = Path(directory) / (name + '_cpython.py')
    src.write_text(text, encoding='utf-8')
    done = subprocess.run([sys.executable, '-B', str(src)], capture_output=True, timeout=120,
                          env=dict(os.environ, PYTHONUTF8='1'))
    return done.stdout.replace(b'\r\n', b'\n'), done.returncode, done.stderr


def _build_and_run(directory, name, text, general):
    src = Path(directory) / (name + '.ail')
    src.write_text(text, encoding='utf-8')
    exe = Path(directory) / ('exe_' + name + ('_g' if general else '_d'))
    env = dict(os.environ, AIL_NO_CACHE='1', AIL_QUIET_FALLBACK='1')
    env.pop('AIL_NO_GENERAL', None)
    if general:
        env['AIL_UNIFIED_FORCE'] = '1'
    else:
        env.pop('AIL_UNIFIED_FORCE', None)
    built = subprocess.run([sys.executable, '-B', str(ROOT / 'ail_chatgpt.py'), 'compile', src.name,
                            '--syntax', 'python', '-o', exe.name], cwd=directory,
                           capture_output=True, text=True, timeout=900, env=env)
    if built.returncode != 0:
        return None, (built.stdout + built.stderr)[-3000:]
    got = subprocess.run([str(exe)], capture_output=True, timeout=120, cwd=directory)
    return (got.stdout.replace(b'\r\n', b'\n'), got.returncode), got.stderr.decode('utf-8', 'replace')[-1500:]


class Fuzz62Tests(unittest.TestCase):
    def check(self, slug, text, rc=0):
        with tempfile.TemporaryDirectory(prefix='ail-fuzz62-') as directory:
            want, got_rc, err = _cpython(directory, slug, text)
            self.assertEqual(got_rc, rc, err)
            for general in (True, False):
                got, build_err = _build_and_run(directory, '%s_%s' % (slug, 'g' if general else 'd'), text, general)
                self.assertIsNotNone(got, '%s (general=%s)\n%s' % (text[:2000], general, build_err))
                self.assertEqual(got, (want, rc), '%s (general=%s)\n%s' % (text[:2000], general, build_err))

    def test_classmethod_receiver(self):
        self.check('classmethod_receiver', CLASSMETHOD_RECEIVER)

    def test_classmethod_calls(self):
        self.check('classmethod_calls', CLASSMETHOD_CALLS)

    def test_recursion_shapes(self):
        self.check('recursion_shapes', RECURSION_SHAPES)


if __name__ == '__main__':
    unittest.main()
