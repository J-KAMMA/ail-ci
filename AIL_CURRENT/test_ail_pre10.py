"""Pre-existing differences from CPython 3.12 seen while reviewing fuzz69: round()'s ndigits.

The general path read `ndigits` as the union's int member before this change, so
`round(x, None)` used 0 (round(x, 0), a float for a float x) and an `__index__` instance
used whatever happened to sit in that member. A user `__round__` also always received an
argument: `round(u, None)` and `round(u)` passed an int/None instead of calling the method
with no argument, so a required ndigits never raised CPython's TypeError.

The programs below compare stdout and exit status with CPython on the general path and the
default build, with values reaching round() directly, through an argument, a list item, an
attribute and a dict value.
"""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent

ROUND_INDEX = r'''class I:
    def __init__(self, v):
        self.v = v
    def __index__(self):
        return self.v


class Bad:
    def __index__(self):
        return 1.5


class H:
    def __init__(self, v):
        self.v = v


def r(x, n):
    try:
        return repr(round(x, n))
    except Exception as e:
        return type(e).__name__ + ": " + str(e)


def through(x, n):
    return r(x, n)


def main():
    vals = [I(2), I(0), I(-2), I(5), I(-5)]
    for i in vals:
        print(r(1.5, i), r(1234.5, i), r(1, i), r(True, i))
    print(r(1.5, Bad()), r([], Bad()), r([], I(2)), r("x", I(2)), r(None, I(2)))
    i = I(0)
    xs = [i]
    d = {"i": i}
    h = H(i)
    print(through(1.5, i), r(1.5, xs[0]), r(1.5, d["i"]), r(1.5, h.v))
    print(r(1.5, I(True)), r(1.5, True), r(1.5, False))
    print(r(-2.5, I(-1)), r(2.5, I(-1)), r(0.0, I(-3)))


main()
'''

ROUND_NONE_NUMERIC = r'''class H:
    def __init__(self, v):
        self.v = v


def r(x, n):
    try:
        return repr(round(x, n))
    except Exception as e:
        return type(e).__name__ + ": " + str(e)


def main():
    n = None
    xs = [None, 2, None]
    d = {"n": None}
    h = H(None)
    print(repr(round(2.5, None)), repr(round(2.5)), repr(round(2.5, 0)))
    print(r(2.5, n), r(2.5, xs[0]), r(3.5, d["n"]), r(2.5, h.v))
    print(r(-2.5, n), r(0.5, n), r(1.5, n), r(123.456, n), r(5, n), r(True, n))
    print(r(2.5, xs[1]), r(2.5, 0), r(2.5, 2), r(1234.5, -2))


main()
'''

ROUND_NOARG = r'''class U:
    def __init__(self, v):
        self.v = v
    def __round__(self, n):
        return ("u", n, self.v)


class A:
    def __round__(self, n=None):
        return ("a", n)


class B:
    def __round__(self, n=2):
        return ("b", n)


class C:
    def __round__(self):
        return ("c",)


class H:
    def __init__(self, u):
        self.u = u


def r0(x):
    try:
        return repr(round(x))
    except Exception as e:
        return type(e).__name__ + ": " + str(e)


def rn(x, n):
    try:
        return repr(round(x, n))
    except Exception as e:
        return type(e).__name__ + ": " + str(e)


def main():
    u = U(1)
    a = A()
    b = B()
    c = C()
    print(r0(u), rn(u, None), rn(u, 2), rn(u, 2.0))
    print(r0(a), rn(a, None), rn(a, 3))
    print(r0(b), rn(b, None), rn(b, 4))
    print(r0(c), rn(c, None))
    xs = [u]
    d = {"u": u}
    h = H(u)
    print(r0(xs[0]), rn(d["u"], None), r0(h.u))


main()
'''


ROUND_LITERAL_DEFAULTS = r'''class F:
    def __round__(self, n=1.5):
        return repr(n)


class S:
    def __round__(self, n="hi"):
        return repr(n)


class E:
    def __round__(self, n=""):
        return repr(n)


class T:
    def __round__(self, n=True):
        return repr(n)


class Z:
    def __round__(self, n=0):
        return repr(n)


class N:
    def __round__(self, n=-3):
        return repr(n)


class H:
    def __init__(self, o):
        self.o = o


def r0(x):
    try:
        return repr(round(x))
    except Exception as e:
        return type(e).__name__ + ": " + str(e)


def rn(x, n):
    try:
        return repr(round(x, n))
    except Exception as e:
        return type(e).__name__ + ": " + str(e)


def through(x):
    return r0(x)


def main():
    f, s, e, t, z, n = F(), S(), E(), T(), Z(), N()
    print(r0(f), rn(f, None), rn(f, 2))
    print(r0(s), rn(s, None), rn(s, 3))
    print(r0(e), rn(e, None))
    print(r0(t), rn(t, None), rn(t, False))
    print(r0(z), rn(z, None), rn(z, 4))
    print(r0(n), rn(n, None), rn(n, 5))
    xs = [f, s]
    d = {"f": f, "s": s}
    h = H(s)
    print(through(xs[0]), rn(xs[1], None), r0(d["f"]), rn(d["s"], 4))
    print(r0(h.o), rn(h.o, None))


main()
'''

ROUND_UNUSED_LITERAL_DEFAULT = r'''class F:
    def __round__(self, n=1.5):
        return n


class S:
    def __round__(self, n="hi"):
        return n


print("ok")
'''

ROUND_NOINDEX_NAME = r'''class NoIndex:
    pass


class Sub(NoIndex):
    pass


class H:
    def __init__(self, n):
        self.n = n


def r(x, n):
    try:
        return repr(round(x, n))
    except Exception as e:
        return type(e).__name__ + ": " + str(e)


def through(x, n):
    return r(x, n)


def main():
    n = NoIndex()
    s = Sub()
    xs = [n, s]
    d = {"n": n, "s": s}
    h = H(n)
    print(r(2.5, n), r(2.5, s), r(2.5, NoIndex()))
    print(through(2.5, n), r(2.5, xs[0]), r(2.5, xs[1]))
    print(r(2.5, d["n"]), r(2.5, d["s"]), r(2.5, h.n))
    print(r(1, n), r(True, s))


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


class Pre10Tests(unittest.TestCase):
    def check(self, slug, text, rc=0):
        with tempfile.TemporaryDirectory(prefix='ail-pre10-') as directory:
            want, got_rc, err = _cpython(directory, slug, text)
            self.assertEqual(got_rc, rc, err)
            for general in (True, False):
                got, build_err = _build_and_run(directory, '%s_%s' % (slug, 'g' if general else 'd'), text, general)
                self.assertIsNotNone(got, '%s (general=%s)\n%s' % (text[:2000], general, build_err))
                self.assertEqual(got, (want, rc), '%s (general=%s)\n%s' % (text[:2000], general, build_err))

    def test_ndigits_index_like(self):
        self.check('round_index', ROUND_INDEX)

    def test_none_ndigits_is_the_one_argument_form(self):
        self.check('round_none_numeric', ROUND_NONE_NUMERIC)

    def test_user_round_without_ndigits(self):
        self.check('round_noarg', ROUND_NOARG)

    def test_user_round_literal_defaults(self):
        self.check('round_literal_defaults', ROUND_LITERAL_DEFAULTS)

    def test_unused_round_literal_defaults_build(self):
        self.check('round_unused_literal_defaults', ROUND_UNUSED_LITERAL_DEFAULT)

    def test_noindex_uses_the_instance_class_name(self):
        self.check('round_noindex_name', ROUND_NOINDEX_NAME)


if __name__ == '__main__':
    unittest.main()
