"""Differential regression for methods read through a class value (job pre169).

CPython lets `C.f` be read as a plain function value: the function is unbound, the caller
passes the instance first, `@staticmethod` has no receiver, and `@classmethod` is bound to the
class it was read through.  Before this job the general path raised
`AttributeError: 'type' object has no attribute 'f'` for `g = C.f`.

The same read through a simple class alias (`K = C; g = K.f`) and the class attributes read
through that alias are covered too.  Every program is compared with CPython on both builds.
"""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent


VALUES = r'''class C:
    base = 100

    def __init__(self, n):
        self.n = n

    def f(self, x, y=5):
        return self.n + x + y

    @staticmethod
    def s(x, y=2):
        return x + y

    @classmethod
    def cm(cls=None, x=3):
        return 100 + x


def main():
    c = C(1)
    f = C.f
    print(f(c, 10), f(c, 10, 20))
    print(C.f(c, 11))
    s = C.s
    print(s(10), s(10, 20), C.s(3))
    cm = C.cm
    print(cm(), cm(4), C.cm(5))


main()
'''

ALIASES = r'''class C:
    tag = "C"

    def __init__(self, n):
        self.n = n

    def f(self, x=1):
        return self.n + x

    @staticmethod
    def s(x=9):
        return x + 1

    @classmethod
    def cm(cls):
        return who(cls)


class D(C):
    pass


def who(c):
    if c is C:
        return "C"
    if c is D:
        return "D"
    return "?"


K = C


def main():
    g = K.f
    print(g(K(2), 3), K.tag, D.tag)
    print(K.f(K(4)), K.cm(), K.s(10))
    h = C.cm
    hm = D.cm
    print(h(), hm(), h(), hm())
    M = D
    gm = M.f
    print(gm(M(5), 1), M.tag)


main()
'''

THROUGH_VALUES = r'''class C:
    def __init__(self, n):
        self.n = n

    def f(self, x):
        return self.n * x

    @staticmethod
    def s(x):
        return x + 1


def get():
    return C.f


def call(f, a, b):
    return f(a, b)


def main():
    c = C(3)
    f = C.f
    s = C.s
    print(call(f, c, 2))
    xs = [f, s]
    print(xs[0](c, 5), xs[1](6))
    d = {"f": f, "s": s}
    print(d["f"](c, 7), d["s"](8))
    print((f, s)[0](c, 9))
    g = f
    print(g(c, 10))
    print(get()(c, 11))


main()
'''

DEFAULTS = r'''calls = [0]


def make():
    calls[0] += 1
    print("make", calls[0])
    return 5


class C:
    def __init__(self, n):
        self.n = n

    def f(self, x=make(), xs=[]):
        xs.append(self.n)
        return self.n + x + len(xs)


def main():
    c = C(1)
    print("read1")
    g = C.f
    print("read2")
    h = C.f
    print(g(c), h(c), C.f(c), calls[0])


main()
'''

ARITY_ERRORS = r'''class C:
    def __init__(self, n):
        self.n = n

    def f(self, x):
        return self.n + x

    @staticmethod
    def s(x):
        return x


def main():
    c = C(1)
    f = C.f
    for which in (0, 1, 2):
        try:
            if which == 0:
                print(f(c))
            elif which == 1:
                print(f(c, 1, 2))
            else:
                print(f())
        except TypeError as e:
            print("TypeError", e)
    s = C.s
    for which in (0, 1):
        try:
            if which == 0:
                print(s())
            else:
                print(s(1, 2))
        except TypeError as e:
            print("TypeError", e)


main()
'''

SHADOWED_CLASS_NAME = r'''class C:
    tag = "class"


def main():
    C = 7
    print(C + 1)
    D = C
    print(D + 2)


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


class Pre169Tests(unittest.TestCase):
    def check(self, slug, text, rc=0):
        with tempfile.TemporaryDirectory(prefix='ail-pre169-') as directory:
            want, got_rc, err = _cpython(directory, slug, text)
            self.assertEqual(got_rc, rc, err)
            for general in (True, False):
                got, build_err = _build_and_run(directory, '%s_%s' % (slug, 'g' if general else 'd'), text, general)
                self.assertIsNotNone(got, '%s (general=%s)\n%s' % (text[:2000], general, build_err))
                self.assertEqual(got, (want, rc), '%s (general=%s)\n%s' % (text[:2000], general, build_err))

    def test_regular_static_and_classmethod_values(self):
        self.check('values', VALUES)

    def test_method_values_through_class_aliases(self):
        self.check('aliases', ALIASES)

    def test_method_values_through_arguments_containers_and_returns(self):
        self.check('through_values', THROUGH_VALUES)

    def test_method_value_defaults_are_fixed_at_definition(self):
        self.check('defaults', DEFAULTS)

    def test_method_value_arity_errors(self):
        self.check('arity_errors', ARITY_ERRORS)

    def test_class_name_shadowing_is_not_a_class_value(self):
        self.check('shadowed_class_name', SHADOWED_CLASS_NAME)


if __name__ == '__main__':
    unittest.main()
