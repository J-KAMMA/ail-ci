"""pre77: a class attribute shadows an inherited @property, for reads and writes.

CPython resolves `obj.NAME` through the MRO and the first class entry wins: a
plain `NAME = value` in a subclass hides a `@property NAME` of a base class
both for reading (the value, not the getter) and for assignment (an instance
attribute is created, a base setter is not called).  The general path used to
call the base getter/setter for every instance of every subclass, whatever the
subclass class body bound.

The programs cover the value reaching the attribute through an argument, a list
item, an attribute and a dict value, aliases, three-class chains, a sibling
class without the attribute, int/str/list/None/float values, annotated class
attributes, class-body order (an assignment after a property wins, a property
after an assignment wins) and programs with an ordinary property, with and
without inheritance, that must keep their old behaviour.  Each program is
built on both builds and compared with CPython.
"""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent

SHADOW_READ = r'''class A:
    @property
    def x(self):
        print("get")
        return 1


class B(A):
    x = 5


b = B()


def f(o):
    return o.x


print(b.x)
print(f(b))
print([b][0].x)


class H:
    def __init__(self, o):
        self.o = o


print(H(b).o.x)
print({"o": b}["o"].x)
c = b
print(c.x)
'''

SHADOW_WRITE = r'''class A:
    @property
    def x(self):
        print("get")
        return 1


class B(A):
    x = 5


b = B()
print(b.x)
b.x = 7
print(b.x)


def setit(o):
    o.x = 9


setit(b)
print(b.x)
c = b
c.x = 10
print(b.x, c.x)
xs = [b]
xs[0].x = 11
print(b.x)


class H:
    def __init__(self, o):
        self.o = o


h = H(b)
h.o.x = 12
print(b.x, h.o.x)
d = {"o": b}
d["o"].x = 13
print(b.x)
'''

SHADOW_SETTER = r'''class A:
    def __init__(self):
        self._x = 1

    @property
    def x(self):
        print("get")
        return self._x

    @x.setter
    def x(self, v):
        print("set")
        self._x = v * 2


class B(A):
    x = 5


b = B()
print(b.x)
b.x = 3
print(b.x)
print(b._x)
'''

SHADOW_CHAIN = r'''class A:
    @property
    def x(self):
        print("A.get")
        return 1


class B(A):
    x = 5


class C(B):
    x = 6


class S(A):
    pass


def show(tag, o):
    print(tag, o.x)


show("A", A())
show("B", B())
show("C", C())
show("S", S())


def setit(o, v):
    o.x = v


b = B()
c = C()
b.x = 7
c.x = 8
print("written", b.x, c.x)
print("base", S().x)
'''

SHADOW_TYPES = r'''class Base:
    @property
    def v(self):
        print("get")
        return 0


class SInt(Base):
    v = 7


class SStr(Base):
    v = "s"


class SList(Base):
    v = []


class SNone(Base):
    v = None


class SFloat(Base):
    v = 1.5


for o in (SInt(), SStr(), SList(), SNone(), SFloat()):
    print(o.v, type(o.v).__name__)
    o.v = 42
    print(o.v)


class Ann:
    @property
    def v(self):
        return 1


class SAnn(Ann):
    v: int = 9


print(SAnn().v)
'''

SHADOW_ORDER = r'''class Q:
    @property
    def x(self):
        print("Q.get")
        return 1

    x = 5


class P:
    x = 5

    @property
    def x(self):
        print("P.get")
        return 2


print(Q().x)
q = Q()
q.x = 8
print(q.x)
print(P().x)
'''

PLAIN_PROPERTY = r'''class Temp:
    def __init__(self):
        self.c = 0

    @property
    def x(self):
        self.c += 1
        return self.c

    @x.setter
    def x(self, v):
        self.c = v * 10


t = Temp()
print(t.x, t.x)
t.x = 3
print(t.x, t.c)


class A:
    def __init__(self):
        self._x = 1

    @property
    def x(self):
        return self._x

    @x.setter
    def x(self, v):
        self._x = v


class B(A):
    pass


b = B()
print(b.x)
b.x = 7
print(b.x)
print(A().x)
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


class Pre77Tests(unittest.TestCase):
    def check(self, slug, text, rc=0):
        with tempfile.TemporaryDirectory(prefix='ail-pre77-') as directory:
            want, got_rc, err = _cpython(directory, slug, text)
            self.assertEqual(got_rc, rc, err)
            for general in (True, False):
                got, build_err = _build_and_run(directory, '%s_%s' % (slug, 'g' if general else 'd'),
                                                text, general)
                self.assertIsNotNone(got, '%s (general=%s)\n%s' % (text[:2000], general, build_err))
                self.assertEqual(got, (want, rc), '%s (general=%s)\n%s' % (text[:2000], general, build_err))

    def test_class_attribute_shadows_base_property_read(self):
        self.check('shadow_read', SHADOW_READ)

    def test_class_attribute_shadows_base_property_write(self):
        self.check('shadow_write', SHADOW_WRITE)

    def test_base_property_setter_is_not_called(self):
        self.check('shadow_setter', SHADOW_SETTER)

    def test_class_attribute_shadow_chain(self):
        self.check('shadow_chain', SHADOW_CHAIN)

    def test_class_attribute_values(self):
        self.check('shadow_types', SHADOW_TYPES)

    def test_class_body_order(self):
        self.check('shadow_order', SHADOW_ORDER)

    def test_plain_and_inherited_properties_unchanged(self):
        self.check('plain_property', PLAIN_PROPERTY)


if __name__ == '__main__':
    unittest.main()
