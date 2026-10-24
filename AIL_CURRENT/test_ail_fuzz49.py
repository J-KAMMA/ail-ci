"""Differential round 49: `a += b` of an instance calls __iadd__ before __add__.

Found with small programs compared against CPython on both builds: on the general
path the argument of an augmented operator was compiled to the runtime helper of
the plain operator (`ail_op_iadd` fell straight back to `ail_op_add`), and
__iadd__ was not in the class dispatch tables at all. A class defining both
printed the __add__ result where CPython mutates and keeps the object:

    class N:
        def __iadd__(self, o):
            self.n += o * 100
            return self
        def __add__(self, o):
            return N(self.n + o)

    a = N(1)
    a += 2
    print(a)          # AIL: N(3)   CPython: N(201)

The same held for `n -= k`, `n *= k`, `n &= k`, `n |= k`, `n ^= k` (the runtime
has ail_op_isub / imul / ibitor / ibitand / ibitxor), for an item of a list or a
dict and for an attribute of an object. The general emitter now dispatches
__iadd__ / __isub__ / __imul__ / __iand__ / __ior__ / __ixor__ for an instance
before the plain operator. A name that is ever the target of an augmented
assignment is never given a trusted class kind: its method may return another
type, as CPython allows, and statements emitted earlier (a loop body, a lambda
made before the assignment) would otherwise use a stale kind. The typed path
already used __iadd__ and is unchanged.

The programs below compare stdout and the exit status with CPython 3.12 on the
general build and on the default build, including the fallbacks that must not
change: a class with only __add__, a reflected method, inheritance, an __iadd__
that returns NotImplemented (then a = a + b), and the primitive augmented
operators.
"""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent

IADD_ONLY = r'''class C:
    def __init__(self, n):
        self.n = n

    def __iadd__(self, o):
        self.n += o * 10
        return self

    def __repr__(self):
        return "C(%d)" % self.n


class H:
    def __init__(self):
        self.c = C(6)

    def bump(self):
        self.c += 7


def main():
    a = C(1)
    a += 2
    print(a)
    xs = [C(2)]
    xs[0] += 3
    print(xs)
    d = {"k": C(4)}
    d["k"] += 5
    print(d["k"])
    h = H()
    h.bump()
    print(h.c)
    try:
        print(a + 2)
    except TypeError:
        print("TypeError")


main()
'''

IADD_WINS = r'''class N:
    def __init__(self, n):
        self.n = n

    def __iadd__(self, o):
        self.n += o * 100
        return self

    def __add__(self, o):
        return N(self.n + o)

    def __repr__(self):
        return "N(%d)" % self.n


def main():
    a = N(1)
    a += 2
    print(a)
    b = N(5)
    b += 1
    print(b)
    c = [N(0)]
    c[0] += 3
    print(c)
    d = {"k": N(0)}
    d["k"] += 4
    print(d["k"])
    print(a + 2)


main()
'''

ISUB_IMUL = r'''class M:
    def __init__(self, x):
        self.x = x

    def __isub__(self, o):
        self.x -= o * 10
        return self

    def __sub__(self, o):
        return M(self.x - o)

    def __imul__(self, o):
        self.x *= o * 10
        return self

    def __mul__(self, o):
        return M(self.x * o)

    def __repr__(self):
        return "M(%d)" % self.x


def main():
    a = M(5)
    a -= 2
    print(a)
    print(a - 1)
    b = M(2)
    b *= 3
    print(b)
    print(b * 2)
    xs = [M(2)]
    xs[0] *= 4
    print(xs)
    ys = [M(9)]
    ys[0] -= 3
    print(ys)


main()
'''

IBITS = r'''class F:
    def __init__(self, x):
        self.x = x

    def __iand__(self, o):
        self.x &= o
        return self

    def __ior__(self, o):
        self.x |= o
        return self

    def __ixor__(self, o):
        self.x ^= o
        return self

    def __and__(self, o):
        return F(self.x & o)

    def __or__(self, o):
        return F(self.x | o)

    def __xor__(self, o):
        return F(self.x ^ o)

    def __repr__(self):
        return "F(%d)" % self.x


def main():
    a = F(6)
    a &= 3
    print(a)
    print(a & 1)
    b = F(6)
    b |= 9
    print(b)
    print(b | 1)
    c = F(6)
    c ^= 3
    print(c)
    print(c ^ 1)


main()
'''

IADD_OTHER_TYPE = r'''class C:
    def __init__(self, n):
        self.n = n

    def __iadd__(self, o):
        return self.n + o * 10

    def __add__(self, o):
        return C(self.n + o)

    def __repr__(self):
        return "C(%d)" % self.n


def main():
    a = C(1)
    a += 2
    print(a)
    print(a + 1)
    b = C(1)
    b += 3
    print(b)
    c = [C(1)]
    c[0] += 2
    print(c[0])


main()
'''

IADD_NOTIMPLEMENTED = r'''class C:
    def __init__(self, n):
        self.n = n

    def __iadd__(self, o):
        return NotImplemented

    def __add__(self, o):
        return C(self.n + o)

    def __radd__(self, o):
        return C(o + self.n)

    def __repr__(self):
        return "C(%d)" % self.n


def main():
    a = C(1)
    a += 2
    print(a)
    print(2 + a)
    a += 10
    print(a)
    b = C(0)
    b += 7
    print(b)


main()
'''

ADD_FALLBACK = r'''class A:
    def __init__(self, n):
        self.n = n

    def __add__(self, o):
        return A(self.n + o)

    def __repr__(self):
        return "A(%d)" % self.n


def main():
    a = A(1)
    a += 2
    print(a)
    xs = [A(1)]
    xs[0] += 3
    print(xs)


main()
'''

LOOP_IADD_CHANGES_TYPE = r'''class B:
    def foo(self):
        return "B"

    def __add__(self, o):
        return B()


class A:
    def __init__(self):
        self.n = 0

    def foo(self):
        return "A"

    def __iadd__(self, o):
        return B()


a = A()
i = 0
while i < 3:
    print(a.foo())
    a += 1
    i += 1
print(type(a).__name__)
print("done")
'''

LAMBDA_IADD_CHANGES_TYPE = r'''class B:
    def foo(self):
        return "B"


class A:
    def __init__(self):
        self.n = 0

    def foo(self):
        return "A"

    def __iadd__(self, o):
        return B()


a = A()
f = lambda: a.foo()
print(f())
a += 1
print(f())
'''

CLOSURE_IADD_CHANGES_TYPE = r'''class B:
    def foo(self):
        return "B"


class A:
    def __init__(self):
        self.n = 0

    def foo(self):
        return "A"

    def __iadd__(self, o):
        return B()


def main():
    a = A()

    def f():
        return a.foo()

    print(f())
    a += 1
    print(f())


main()
'''

REFLECTED = r'''class R:
    def __init__(self, n):
        self.n = n

    def __radd__(self, o):
        return R(self.n + o * 10)

    def __rsub__(self, o):
        return R(o * 10 - self.n)

    def __rmul__(self, o):
        return R(self.n * o * 10)

    def __repr__(self):
        return "R(%d)" % self.n


def main():
    r = R(2)
    print(3 + r)
    print(10 - r)
    print(3 * r)
    print(r)
    try:
        r += 3
    except TypeError:
        print("TypeError")
    print(r)


main()
'''

INHERITED = r'''class Base:
    def __init__(self, n):
        self.n = n

    def __iadd__(self, o):
        self.n += o * 10
        return self

    def __repr__(self):
        return "B(%d)" % self.n


class Sub(Base):
    pass


def main():
    s = Sub(1)
    s += 2
    print(s, isinstance(s, Sub))


main()
'''

PLAIN_AUG = r'''def main():
    n = 1
    n += 2
    f = 1.5
    f *= 2
    xs = [1, 2]
    xs += [3]
    xs *= 2
    s = "a"
    s += "b"
    b = 6
    b &= 3
    b |= 8
    b ^= 1
    t = (1, 2)
    t += (3,)
    print(n, f, xs, s, b, t)


main()
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


class Fuzz49Tests(unittest.TestCase):
    def check(self, slug, text, rc=0):
        with tempfile.TemporaryDirectory(prefix='ail-fuzz49-') as directory:
            want, got_rc, err = _cpython(directory, slug, text)
            self.assertEqual(got_rc, rc, err)
            for general in (True, False):
                got, build_err = _build_and_run(directory, '%s_%s' % (slug, 'g' if general else 'd'), text, general)
                self.assertIsNotNone(got, '%s (general=%s)\n%s' % (text[:2000], general, build_err))
                self.assertEqual(got, (want, rc), '%s (general=%s)\n%s' % (text[:2000], general, build_err))

    def test_iadd_only(self):
        self.check('iadd_only', IADD_ONLY)

    def test_iadd_wins_over_add(self):
        self.check('iadd_wins', IADD_WINS)

    def test_isub_and_imul(self):
        self.check('isub_imul', ISUB_IMUL)

    def test_inplace_bitwise(self):
        self.check('ibits', IBITS)

    def test_iadd_returns_another_type(self):
        self.check('iadd_other_type', IADD_OTHER_TYPE)

    def test_iadd_notimplemented_falls_back(self):
        self.check('iadd_notimplemented', IADD_NOTIMPLEMENTED)

    def test_add_fallback_unchanged(self):
        self.check('add_fallback', ADD_FALLBACK)

    def test_loop_iadd_changes_type(self):
        self.check('loop_iadd_type', LOOP_IADD_CHANGES_TYPE)

    def test_lambda_before_iadd_changes_type(self):
        self.check('lambda_iadd_type', LAMBDA_IADD_CHANGES_TYPE)

    def test_closure_before_iadd_changes_type(self):
        self.check('closure_iadd_type', CLOSURE_IADD_CHANGES_TYPE)

    def test_reflected_operators_unchanged(self):
        self.check('reflected', REFLECTED)

    def test_inherited_iadd(self):
        self.check('inherited', INHERITED)

    def test_plain_augmented_unchanged(self):
        self.check('plain_aug', PLAIN_AUG)


if __name__ == '__main__':
    unittest.main()
