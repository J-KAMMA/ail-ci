"""Pre-300: a class body reads its own earlier assignment before a module class of that name.

``class B: A = C; y = A.x`` used to resolve ``A`` to the module class ``A`` (printing 12 instead
of CPython's 7), and a class-local class without the attribute printed the module class's 2**59
instead of raising AttributeError.  The general path now keeps the class namespace of the body
being evaluated, so an earlier assignment shadows the module class for the rest of that body
(including values reaching the read through an argument, a list item, an attribute and a dict
value, and a repeated assignment's last value).  A method default that would need the same class
scope is refused by name, because method defaults are built at the call site here.  A class local
that holds a class is treated like the direct class value it names: static, class and instance
methods called through it match CPython, while reading a method/property off it stays a named
refusal instead of falling through to the run time's method/property error.
"""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent

MATCH = {
    'direct_alias': '''class A:
    x = 12


class C:
    x = 7


class B:
    A = C
    y = A.x


print(B.y)
''',
    'bignum_attribute': '''class K:
    N = 2**59


class C:
    N = 0


class A:
    K = C
    y = K.N


print(A.y)
''',
    'missing_attribute': '''class K:
    N = 2**59


class C:
    M = 1


class A:
    K = C
    y = K.N


print(A.y)
''',
    'duplicate_last_wins': '''class C:
    x = 7


class D:
    x = 9


class B:
    A = C
    A = D
    y = A.x


print(B.y)
''',
    'plain_value': '''X = 12


class B:
    X = 7
    y = X + 1


print(B.y)
''',
    'value_types': '''class A:
    i = 12
    f = 1.5
    s = "aa"
    b = True
    n = -2


class C:
    i = 7
    f = -0.5
    s = ""
    b = False
    n = 0


class B:
    A = C
    i = A.i
    f = A.f
    s = A.s
    b = A.b
    n = A.n


print(B.i, B.f, repr(B.s), B.b, B.n)
''',
    'argument_route': '''def get_x(cls):
    return cls.x


class A:
    x = 12


class C:
    x = 7


class B:
    A = C
    y = get_x(A)


print(B.y)
''',
    'container_routes': '''class C:
    x = 7


class D:
    x = 9


holder = D()
lst = [C]
mapping = {"k": C}


class A:
    P = lst[0]
    Q = mapping["k"]
    R = holder
    a = P.x
    b = Q.x
    c = R.x


print(A.a, A.b, A.c)
''',
    'self_reference_is_module_class': '''class K:
    N = 2**59


class A:
    K = K
    y = K.N


print(A.y)
''',
    'comprehension_keeps_module_scope': '''class A:
    x = 12


class C:
    x = 7


class B:
    A = C
    y = [A.x for _ in range(1)]


print(B.y)
''',
    'class_value_static_method': '''class C:
    @staticmethod
    def get():
        return 42


class B:
    A = C
    y = A.get()


print(B.y)
''',
    'class_value_classmethod': '''class C:
    x = 7

    @classmethod
    def get(cls):
        return cls.x


class B:
    A = C
    y = A.get()


print(B.y)
''',
    'class_value_instance_method': '''class C:
    def m(self):
        return 7


class B:
    A = C
    y = A.m(C())


print(B.y)
''',
    'class_value_method_alias': '''class C:
    def m(self):
        return 7


class B:
    A = C
    D = A
    y = D.m(C())


print(B.y)
''',
    'class_value_static_list': '''class C:
    @staticmethod
    def get():
        return 42


lst = [C]


class B:
    A = lst[0]
    y = A.get()


print(B.y)
''',
    'class_value_classmethod_argument': '''class C:
    x = 7

    @classmethod
    def get(cls):
        return cls.x


def take(value):
    return value


class B:
    A = take(C)
    y = A.get()


print(B.y)
''',
    'class_value_instance_method_dict': '''class C:
    def m(self):
        return 7


mapping = {"k": C}


class B:
    A = mapping["k"]
    y = A.m(C())


print(B.y)
''',
    'instance_property_routes': '''class C:
    x = 7

    @property
    def p(self):
        return self.x


class Holder:
    def __init__(self):
        self.c = C()


items = [C()]
holder = Holder()


class B:
    A = items[0]
    D = holder.c
    y = A.p
    z = D.p


print(B.y, B.z)
''',
}

REFUSED = {
    'method_default': ('''class A:
    x = 12


class C:
    x = 7


class B:
    A = C

    def f(self, v=A.x):
        return v


print(B().f())
''', 'a method default that reads the class-body local'),
    'property_read': ('''class C:
    x = 7

    @property
    def p(self):
        return self.x


class B:
    A = C
    y = A.p


print(B.y)
''', 'reading property C.p through a class value'),
    'method_read': ('''class C:
    def m(self):
        return 7


class B:
    A = C
    y = A.m


print(type(B.y).__name__)
''', 'reading method C.m through a class value'),
    'property_read_list': ('''class C:
    x = 7

    @property
    def p(self):
        return self.x


items = [C]


class B:
    A = items[0]
    y = A.p


print(B.y)
''', 'reading property C.p through a class value'),
    'property_read_attribute': ('''class C:
    x = 7

    @property
    def p(self):
        return self.x


class Holder:
    def __init__(self):
        self.c = C


holder = Holder()


class B:
    A = holder.c
    y = A.p


print(B.y)
''', 'reading property C.p through a class value'),
    'method_read_argument': ('''class C:
    def m(self):
        return 7


def get():
    return C


class B:
    A = get()
    y = A.m


print(type(B.y).__name__)
''', 'reading method C.m through a class value'),
}


def _cpython(directory, name, text):
    src = Path(directory) / (name + '_cpython.py')
    src.write_text(text, encoding='utf-8')
    done = subprocess.run([sys.executable, '-B', str(src)], capture_output=True, timeout=120,
                          env=dict(os.environ, PYTHONUTF8='1'))
    return done.stdout.replace(b'\r\n', b'\n'), done.returncode


def _build(directory, name, text, general):
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
    return built, exe


class Pre300Tests(unittest.TestCase):
    def matches(self, slug, text):
        with tempfile.TemporaryDirectory(prefix='ail-pre300-') as directory:
            want, want_rc = _cpython(directory, slug, text)
            for general in (True, False):
                name = '%s_%s' % (slug, 'g' if general else 'd')
                built, exe = _build(directory, name, text, general)
                self.assertEqual(built.returncode, 0,
                                 '%s (general=%s)\n%s' % (slug, general, (built.stdout + built.stderr)[-3000:]))
                got = subprocess.run([str(exe)], capture_output=True, timeout=120, cwd=directory)
                self.assertEqual((got.stdout.replace(b'\r\n', b'\n'), got.returncode), (want, want_rc),
                                 '%s (general=%s)' % (slug, general))

    def refused(self, slug, text, needle):
        with tempfile.TemporaryDirectory(prefix='ail-pre300-') as directory:
            for general in (True, False):
                name = '%s_%s' % (slug, 'g' if general else 'd')
                built, exe = _build(directory, name, text, general)
                output = built.stdout + built.stderr
                self.assertNotEqual(built.returncode, 0, '%s (general=%s)\n%s' % (slug, general, output[-3000:]))
                self.assertIn(needle, output, '%s (general=%s)\n%s' % (slug, general, output[-3000:]))
                self.assertFalse(exe.exists(), '%s (general=%s) built an executable' % (slug, general))

    def test_class_body_local_shadow_matches_cpython(self):
        for slug, text in MATCH.items():
            with self.subTest(case=slug):
                self.matches(slug, text)

    def test_refused_by_name(self):
        for slug, (text, needle) in REFUSED.items():
            with self.subTest(case=slug):
                self.refused(slug, text, needle)


if __name__ == '__main__':
    unittest.main()
