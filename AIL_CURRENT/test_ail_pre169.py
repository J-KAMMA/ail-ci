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


ALIAS_USE_BEFORE_ASSIGN = r'''class C:
    tag = "C"

    def __init__(self, n):
        self.n = n

    def f(self, x):
        return self.n + x

    @staticmethod
    def s(x):
        return x * 2

    @classmethod
    def cm(cls, x):
        return 100 + x


def call(fn, c, x):
    return fn(c, x)


def main():
    for label, use in (
            ("method", lambda: K.f(C(1), 2)),
            ("attr", lambda: K.tag),
            ("direct", lambda: K.f(C(1), 3)),
            ("static", lambda: K.s(6)),
            ("cm", lambda: K.cm(4)),
            ("container", lambda: [K.f, K.s][0](C(1), 5)),
            ("passed", lambda: call(K.f, C(1), 6))):
        try:
            print(label, use())
        except NameError:
            print(label, "NameError")

    def inner():
        try:
            return K.f(C(1), 7)
        except NameError:
            return "NameError"
    print("nested", inner())


main()
K = C
'''

ALIAS_DELETED = r'''class C:
    tag = "C"

    def __init__(self, n):
        self.n = n

    def f(self, x):
        return self.n + x

    @classmethod
    def cm(cls, x):
        return 50 + x


K = C
del K


def main():
    for label, use in (
            ("method", lambda: K.f(C(1), 2)),
            ("attr", lambda: K.tag),
            ("direct", lambda: K.f(C(1), 3)),
            ("cm", lambda: K.cm(4))):
        try:
            print(label, use())
        except NameError:
            print(label, "NameError")


main()
'''

ALIAS_BEFORE_CLASS = r'''print("start")
K = C
print("unreachable")

class C:
    tag = "C"

    def __init__(self, n):
        self.n = n

    def f(self, x):
        return self.n + x


def main():
    g = K.f
    print(g(K(1), 2), K.tag)


main()
'''

CLASSMETHOD_VALUE_ARITY = r'''class C:
    @classmethod
    def only(cls):
        return "only"

    @classmethod
    def one(cls, x):
        return x + 1

    @classmethod
    def opt(cls, x=5):
        return x + 2

    @classmethod
    def two(cls, x, y=10):
        return x + y


class D(C):
    pass


K = C
M = D


def run(label, call):
    try:
        print(label, call())
    except TypeError as e:
        print(label, "TypeError", e)


def main():
    only = C.only
    one = C.one
    opt = C.opt
    two = C.two
    run("only0", lambda: only())
    run("only1", lambda: only(1))
    run("one0", lambda: one())
    run("one1", lambda: one(2))
    run("one2", lambda: one(2, 3))
    run("opt0", lambda: opt())
    run("opt1", lambda: opt(4))
    run("opt2", lambda: opt(4, 5))
    run("two0", lambda: two())
    run("two1", lambda: two(6))
    run("two2", lambda: two(6, 7))
    run("two3", lambda: two(6, 7, 8))
    alias = K.one
    run("alias", lambda: alias(9))
    run("alias_bad", lambda: alias(9, 10))
    run("sub", lambda: M.two(11))


main()
'''


INHERITED_METHOD_ARITY = r'''class C:
    def f(self, x):
        return x

    @staticmethod
    def s(x):
        return x

    @classmethod
    def cm(cls, x):
        return x


class D(C):
    pass


K = D


def run(label, call):
    try:
        print(label, call())
    except TypeError as e:
        print(label, "TypeError", e)


def main():
    f = D.f
    s = K.s
    cm = K.cm
    run("f0", lambda: f())
    run("f1", lambda: f(1))
    run("f2", lambda: f(1, 2))
    run("f3", lambda: f(1, 2, 3))
    run("s0", lambda: s())
    run("s2", lambda: s(1, 2))
    run("cm0", lambda: cm())
    run("cm2", lambda: cm(1, 2))


main()
'''


ALIAS_MODULE_FLOW = r'''class C:
    tag = "C"

    def __init__(self, n):
        self.n = n

    def f(self, x):
        return self.n + x


try:
    g = K.f
    print("got", g(C(1), 2))
except NameError:
    print("NameError method")

try:
    print(K.tag)
except NameError:
    print("NameError attr")

K = C

try:
    print("after", K.f(C(1), 3), K.tag)
except NameError:
    print("unexpected NameError")

del K

try:
    print(K.f(C(1), 4))
except NameError:
    print("NameError after del")
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

    def test_module_alias_use_before_assignment(self):
        self.check('alias_use_before', ALIAS_USE_BEFORE_ASSIGN)

    def test_module_alias_after_del(self):
        self.check('alias_deleted', ALIAS_DELETED)

    def test_module_alias_before_class_definition(self):
        self.check('alias_before_class', ALIAS_BEFORE_CLASS, rc=1)

    def test_classmethod_value_arity_errors(self):
        self.check('classmethod_value_arity', CLASSMETHOD_VALUE_ARITY)

    def test_inherited_method_value_arity_names_the_defining_class(self):
        self.check('inherited_method_arity', INHERITED_METHOD_ARITY)

    def test_module_alias_binding_at_module_scope(self):
        self.check('alias_module_flow', ALIAS_MODULE_FLOW)


if __name__ == '__main__':
    unittest.main()
