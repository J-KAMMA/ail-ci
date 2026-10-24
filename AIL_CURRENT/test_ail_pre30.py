"""pre30: a bound method read as a value is refused by name.

CPython makes `f = c.m` a bound-method object.  This compiler has no such
value, and used to compile the read as an ordinary attribute fetch, so the
program died at run time with `AttributeError: 'C' object has no attribute
'm'`.  Both emitters now refuse the read at compile time, naming the method.
Direct calls, properties, class attributes, static/class methods and ordinary
function values keep working.
"""
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent
HAVE_CC = shutil.which('gcc') is not None


def cpython(directory, name, text):
    src = Path(directory) / (name + '_cpython.py')
    src.write_text(text, encoding='utf-8')
    done = subprocess.run([sys.executable, '-B', str(src)], capture_output=True, timeout=120,
                          env=dict(os.environ, PYTHONUTF8='1'))
    return done.stdout.replace(b'\r\n', b'\n'), done.returncode


def build(directory, name, text, general):
    src = Path(directory) / (name + '.ail')
    src.write_text(text, encoding='utf-8')
    exe = Path(directory) / ('exe_' + name + ('_g' if general else '_d'))
    env = dict(os.environ, AIL_NO_CACHE='1', AIL_QUIET_FALLBACK='1')
    env.pop('AIL_NO_GENERAL', None)
    if general:
        env['AIL_UNIFIED_FORCE'] = '1'
    else:
        env.pop('AIL_UNIFIED_FORCE', None)
    done = subprocess.run([sys.executable, '-B', str(ROOT / 'ail_chatgpt.py'), 'compile', src.name,
                           '--syntax', 'python', '-o', exe.name], cwd=directory,
                          capture_output=True, text=True, timeout=900, env=env)
    return exe, done


def check_refused(test, name, text, marker='bound method'):
    with tempfile.TemporaryDirectory(prefix='ail-pre30-') as directory:
        for general in (True, False):
            _, built = build(directory, '%s_%s' % (name, 'g' if general else 'd'), text, general)
            test.assertNotEqual(built.returncode, 0, (name, general))
            message = built.stdout + built.stderr
            test.assertIn(marker, message, (name, general, message[-1500:]))


def check_matches(test, name, text):
    with tempfile.TemporaryDirectory(prefix='ail-pre30-') as directory:
        want, want_rc = cpython(directory, name, text)
        for general in (True, False):
            exe, built = build(directory, '%s_%s' % (name, 'g' if general else 'd'), text, general)
            test.assertEqual(built.returncode, 0, (name, general, (built.stdout + built.stderr)[-1500:]))
            got = subprocess.run([str(exe)], capture_output=True, timeout=120, cwd=directory)
            test.assertEqual(got.stdout.replace(b'\r\n', b'\n'), want, (name, general, got.stderr[-1000:]))
            test.assertEqual(got.returncode, want_rc, (name, general, got.stderr[-1000:]))


REFUSED = {
    'local': '''
class C:
    def __init__(self, n):
        self.n = n
    def add(self, x):
        return self.n + x


def main():
    c = C(4)
    f = c.add
    print(f(1))


main()
''',
    'alias': '''
class C:
    def __init__(self, n):
        self.n = n
    def add(self, x):
        return self.n + x


def main():
    c = C(4)
    f = c.add
    g = f
    print(g(1))


main()
''',
    'argument': '''
class C:
    def __init__(self, n):
        self.n = n
    def add(self, x):
        return self.n + x


def take(f):
    return f(3)


def main():
    c = C(8)
    print(take(c.add))


main()
''',
    'list_item': '''
class C:
    def __init__(self, n):
        self.n = n
    def add(self, x):
        return self.n + x


def main():
    c = C(2)
    fs = [c.add]
    print(fs[0](5))


main()
''',
    'attribute': '''
class C:
    def __init__(self, n):
        self.n = n
    def add(self, x):
        return self.n + x


class Holder:
    def __init__(self):
        self.f = None


def main():
    c = C(6)
    h = Holder()
    h.f = c.add
    print(h.f(2))


main()
''',
    'dict_value': '''
class C:
    def __init__(self, n):
        self.n = n
    def add(self, x):
        return self.n + x


def main():
    c = C(9)
    d = {"add": c.add}
    print(d["add"](-4))


main()
''',
    'classmethod': '''
class C:
    base = 100
    def __init__(self, n):
        self.n = n
    @classmethod
    def make(cls, n):
        return cls(n)


def main():
    c = C(1)
    f = c.make
    print(f(7).n)


main()
''',
    'staticmethod': '''
class C:
    @staticmethod
    def twice(x):
        return x * 2


def main():
    c = C()
    f = c.twice
    print(f(5))


main()
''',
    'subclass': '''
class A:
    def m(self):
        return 1


class B(A):
    pass


def main():
    b = B()
    f = b.m
    print(f())


main()
''',
    'subclass_method_over_base_attr': '''
class A:
    m = 5
    def __init__(self):
        self.n = 0


class B(A):
    def m(self):
        return 1


def main():
    f = B().m
    print(f())


main()
''',
    'classattr_then_method': '''
class C:
    m = 5
    def m(self):
        return 1


def main():
    f = C().m
    print(f())


main()
''',
}

ALLOWED = '''
class P:
    scale = 3
    def __init__(self, n):
        self.n = n
    def add(self, x):
        return self.n + x
    @property
    def doubled(self):
        return self.n * 2
    @staticmethod
    def twice(x):
        return x * 2
    @classmethod
    def make(cls, n):
        return cls(n)


def inc(x):
    return x + 1


def main():
    p = P(-10)
    print(p.add(5), p.doubled, P.scale)
    print(p.twice(4), p.make(7).n)
    f = inc
    print(f(9))
    print(P(-2).add(3))


main()
'''


SHADOWED = {
    'field_shadow_own': '''
class C:
    def __init__(self):
        self.m = 5
    def m(self):
        return 1
c = C(); print(c.m)
''',
    'field_shadow_inherited': '''
class A:
    def x(self):
        return 1
class B(A):
    def __init__(self):
        self.x = 7
print(B().x)
''',
    'classattr_shadows_base_method': '''
class A:
    def m(self):
        return 1
class B(A):
    m = 5
    def __init__(self):
        self.n = 0
print(B().m)
''',
    'field_set_in_other_method': '''
class C:
    def __init__(self):
        self.n = 0
    def m(self):
        return 1
    def set(self):
        self.m = -3
c = C(); c.set(); print(c.m)
''',
    'inherited_field_shadows_method': '''
class A:
    def __init__(self):
        self.x = -8
    def x(self):
        return 1
class B(A):
    pass
print(B().x)
''',
    'same_class_attr_after_method': '''
class C:
    def m(self):
        return 1
    m = 5
print(C().m)
''',
    'classattr_base_method_subclass': '''
class A:
    def m(self):
        return 1
class B(A):
    m = 5
class C(B):
    pass
print(C().m)
''',
    'classattr_in_base': '''
class A:
    m = 5
    def __init__(self):
        self.n = 0
class B(A):
    pass
print(B().m)
''',
    'subclass_method_over_base_attr_call': '''
class A:
    m = 5
    def __init__(self):
        self.n = 0
class B(A):
    def m(self):
        return 1
print(B().m())
''',
    'field_via_argument': '''
class A:
    def m(self):
        return 1
class B(A):
    def __init__(self):
        self.m = 7
def show(a):
    print(a.m)
show(B())
''',
    'field_via_list': '''
class A:
    def m(self):
        return 1
class B(A):
    def __init__(self):
        self.m = 7
print([B()][0].m)
''',
    'field_via_attribute': '''
class A:
    def m(self):
        return 1
class B(A):
    def __init__(self):
        self.m = 7
class H:
    def __init__(self):
        self.b = B()
print(H().b.m)
''',
    'field_via_dict': '''
class A:
    def m(self):
        return 1
class B(A):
    def __init__(self):
        self.m = 7
print({"b": B()}["b"].m)
''',
}


@unittest.skipUnless(HAVE_CC, 'gcc is required')
class BoundMethodValueTests(unittest.TestCase):
    def test_bound_method_value_is_refused_by_name(self):
        for name, text in sorted(REFUSED.items()):
            marker = 'method' if name == 'staticmethod' else 'bound method'
            check_refused(self, name, text, marker)

    def test_calls_properties_and_function_values_still_match_cpython(self):
        check_matches(self, 'allowed', ALLOWED)

    def test_fields_and_class_attributes_shadowing_methods_match_cpython(self):
        for name, text in sorted(SHADOWED.items()):
            check_matches(self, name, text)


if __name__ == '__main__':
    unittest.main()
