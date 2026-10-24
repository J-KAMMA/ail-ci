"""Pre-existing property reads from a class, and a class attribute shadowing a base property.

`C.p` where `p` is a `@property` is a property object in CPython.  The general path used to run the
getter only for an instance and then look `C.p` up as an instance attribute, so it died with
`AttributeError: 'type' object has no attribute 'p'`.  A property object is not modelled, so reading
one from a class is now refused by name (DIFFERENCES C?-job-pre53-10241240-1).  The same lookup also
called a base class's getter for a subclass that binds the name as a class attribute (`B().x` printed
the parent's value instead of `B.x`); the class attribute now shadows the base property, as in
CPython.  Programs are built with the general path forced and with the default build.
"""
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent
CHATGPT = str(ROOT / 'ail_chatgpt.py')
HAVE_CC = shutil.which('gcc') is not None
MARKER = 'C?-job-pre53-10241240-1'


def cpython(directory, name, text):
    src = Path(directory) / (name + '_cpython.py')
    src.write_text(text, encoding='utf-8')
    done = subprocess.run([sys.executable, '-B', str(src)], capture_output=True, timeout=120,
                          env=dict(os.environ, PYTHONUTF8='1', PYTHONWARNINGS='ignore'))
    return done.stdout.replace(b'\r\n', b'\n'), done.returncode


def build(directory, name, text, general):
    src = Path(directory) / (name + '.ail')
    src.write_text(text, encoding='utf-8')
    exe = Path(directory) / ('exe_' + name + ('_g' if general else '_d'))
    env = dict(os.environ, AIL_NO_CACHE='1', AIL_QUIET_FALLBACK='1')
    env.pop('AIL_NO_GENERAL', None)
    if general:
        env['AIL_UNIFIED_FORCE'] = '1'
    return exe, subprocess.run([sys.executable, '-B', CHATGPT, 'compile', src.name, '--syntax', 'python',
                                '-o', exe.name], cwd=directory, capture_output=True, text=True, timeout=900, env=env)


def check_program(test, name, text):
    with tempfile.TemporaryDirectory(prefix='ail-pre53-') as directory:
        want = cpython(directory, name, text)
        for general in (True, False):
            exe, built = build(directory, name + ('g' if general else 'd'), text, general)
            test.assertEqual(built.returncode, 0, built.stdout + built.stderr)
            got = subprocess.run([str(exe)], capture_output=True, timeout=120, cwd=directory)
            test.assertEqual(got.stdout.replace(b'\r\n', b'\n'), want[0], (name, general, got.stderr[-800:]))
            test.assertEqual(got.returncode, want[1], (name, general, got.stderr[-800:]))


def check_refused(test, name, text):
    with tempfile.TemporaryDirectory(prefix='ail-pre53-') as directory:
        for general in (True, False):
            _, built = build(directory, name + ('g' if general else 'd'), text, general)
            test.assertNotEqual(built.returncode, 0, (name, general))
            message = built.stdout + built.stderr
            test.assertIn(MARKER, message, (name, general, message[-1200:]))
            test.assertIn('property object', message, (name, general, message[-1200:]))


PROPERTY_FROM_CLASS = {
    'direct': '''
class C:
    def __init__(self):
        self._x = 3

    @property
    def p(self):
        return self._x


def main():
    print(C.p)


main()
''',
    'alias': '''
class C:
    @property
    def p(self):
        return 1


D = C


def main():
    print(D.p)


main()
''',
    'through_argument': '''
class C:
    @property
    def p(self):
        return 1


def show(o):
    print(type(o.p).__name__)


def main():
    show(C)


main()
''',
    'through_list_item': '''
class C:
    @property
    def p(self):
        return 1


def main():
    xs = [C]
    print(type(xs[0].p).__name__)


main()
''',
    'through_dict_value': '''
class C:
    @property
    def p(self):
        return 1


def main():
    d = {'k': C}
    print(type(d['k'].p).__name__)


main()
''',
    'through_attribute': '''
class C:
    @property
    def p(self):
        return 1


class H:
    pass


def main():
    h = H()
    h.o = C
    print(type(h.o.p).__name__)


main()
''',
    'inherited': '''
class A:
    @property
    def p(self):
        return 1


class B(A):
    pass


def main():
    q = B.p
    print(q.fget is not None)


main()
''',
}

SHADOWED = {
    'subclass_class_attribute': '''
class A:
    @property
    def x(self):
        return 1


class B(A):
    x = 2


class C(A):
    @property
    def x(self):
        return 3


class D(B):
    pass


class E(C):
    pass


class H:
    def __init__(self, o):
        self.o = o


def show(o):
    return o.x


def main():
    print(A().x, B().x, C().x, D().x, E().x)
    print(show(A()), show(B()), show(C()), show(D()), show(E()))
    xs = [B(), C()]
    print([o.x for o in xs], xs[0].x, xs[1].x)
    d = {'b': B(), 'c': C()}
    print(d['b'].x, d['c'].x)
    print(H(B()).o.x, H(C()).o.x)
    print(B.x, D.x)


main()
''',
    'unrelated_properties_and_instance_attribute': '''
class P:
    @property
    def y(self):
        return 10


class Q:
    @property
    def y(self):
        return 20


class R(Q):
    y = 'shadow'


class T(R):
    def __init__(self):
        self.y = 99


def main():
    print(P().y, Q().y, R().y, T().y)


main()
''',
    'ordinary_property_reads': '''
class Base:
    def __init__(self):
        self._v = 4

    @property
    def v(self):
        return self._v


class Child(Base):
    @property
    def v(self):
        return 40


class Plain:
    pass


def main():
    b = Base()
    c = Child()
    print(b.v, c.v, isinstance(c, Base))
    ps = [b, c]
    print([p.v for p in ps])


main()
''',
}


REBOUND_TO_INSTANCES = {
    'field': '''
class C:
    @property
    def p(self):
        return 1


class H:
    pass


def main():
    h = H()
    h.o = C
    h.o = C()
    print(h.o.p)


main()
''',
    'list_item': '''
class C:
    @property
    def p(self):
        return 1


def main():
    xs = [C]
    xs[0] = C()
    print(xs[0].p)


main()
''',
    'list_append': '''
class C:
    @property
    def p(self):
        return 1


def main():
    xs = [C]
    xs.append(C())
    print(xs[1].p)


main()
''',
    'list_extend': '''
class C:
    @property
    def p(self):
        return 1


def main():
    xs = [C]
    xs.extend([C()])
    print(xs[1].p)


main()
''',
    'list_delitem': '''
class C:
    @property
    def p(self):
        return 1


def main():
    xs = [C, C()]
    del xs[0]
    print(xs[0].p)


main()
''',
    'dict_value': '''
class C:
    @property
    def p(self):
        return 1


def main():
    d = {'k': C}
    d['k'] = C()
    print(d['k'].p)


main()
''',
    'field_through_argument': '''
class C:
    @property
    def p(self):
        return 1


class H:
    pass


def reset(o):
    o.o = C()


def main():
    h = H()
    h.o = C
    reset(h)
    print(h.o.p)


main()
''',
    'list_through_argument': '''
class C:
    @property
    def p(self):
        return 1


def reset(xs):
    xs[0] = C()


def main():
    xs = [C]
    reset(xs)
    print(xs[0].p)


main()
''',
    'dict_through_argument': '''
class C:
    @property
    def p(self):
        return 1


def reset(d):
    d['k'] = C()


def main():
    d = {'k': C}
    reset(d)
    print(d['k'].p)


main()
''',
    'dict_update': '''
class C:
    @property
    def p(self):
        return 1


def main():
    d = {'k': C}
    d.update(k=C())
    print(d['k'].p)


main()
''',
}


@unittest.skipUnless(HAVE_CC, 'gcc is required')
class PropertyFromClass(unittest.TestCase):
    def test_refused_by_name(self):
        for name, text in sorted(PROPERTY_FROM_CLASS.items()):
            with self.subTest(name):
                check_refused(self, 'refuse_' + name, text)


@unittest.skipUnless(HAVE_CC, 'gcc is required')
class ClassDataReboundToInstances(unittest.TestCase):
    def test_mutation_drops_the_class_record(self):
        for name, text in sorted(REBOUND_TO_INSTANCES.items()):
            with self.subTest(name):
                check_program(self, 'rebound_' + name, text)


@unittest.skipUnless(HAVE_CC, 'gcc is required')
class PropertyShadowing(unittest.TestCase):
    def test_class_attribute_shadows_base_property(self):
        for name, text in sorted(SHADOWED.items()):
            with self.subTest(name):
                check_program(self, 'shadow_' + name, text)
