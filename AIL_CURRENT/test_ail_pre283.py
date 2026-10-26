"""Pre-283: a class-attribute store through a class value is refused by name.

``class Box: v = 1.0`` followed by ``Box.v = 2.5`` prints 2.5 on CPython, but both builds raised
``AttributeError: 'type' object has no attribute 'v'``: the general path keeps each class attribute
in a slot it only reads and copies onto instances, so it cannot store through the class object.
A store whose base is statically a class is now refused at compile time, by name:

* a direct class name by the emitters -- the typed path keeps its own class-attribute support
  (a class with an __init__ still matches CPython on the default build, and the general build
  refuses it by name);
* an alias of a class, or a class read out of a literal list/tuple/dict (constant index, negative
  or not), by the front end on both builds.

A base that only holds a class at run time (a parameter, an instance attribute, a container that
is aliased or mutated) is refused by the runtime under the same name.  Stores through instances
and through names shadowed by a local, a parameter, a loop target or a closure cell are unchanged
and still match CPython on both builds.
"""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent

DIRECT = {
    'module': '''class Box:
    v = 1.0


Box.v = 2.5
print(Box.v)
''',
    'function': '''class Box:
    v = 1.0


def setv():
    Box.v = 2.5


setv()
print(Box.v)
''',
    'augassign': '''class Box:
    v = 1.0


Box.v += 1.5
print(Box.v)
''',
    'annotated': '''class Box:
    v = 1.0


Box.v: float = 2.5
print(Box.v)
''',
    'new_attribute': '''class Box:
    v = 1.0


Box.w = 7
print(Box.w)
''',
    'method': '''class Box:
    v = 1.0

    def setv(self):
        Box.v = 2.5


Box().setv()
print(Box.v)
''',
    'inherited': '''class A:
    K = 3


class B(A):
    pass


B.K = 4
print(B.K)
''',
}

ALIAS = {
    'module': '''class Box:
    v = 1.0


B = Box
B.v = 2.5
print(B.v, Box.v)
''',
    'local': '''class Box:
    v = 1.0


def setv():
    B = Box
    B.v = 2.5


setv()
print(Box.v)
''',
    'module_alias_read_in_function': '''class Box:
    v = 1.0


B = Box


def setv():
    B.v = 2.5


setv()
print(Box.v)
''',
}

CONTAINER = {
    'list': '''class Box:
    v = 1.0


xs = [Box]
xs[0].v = 2.5
print(Box.v)
''',
    'tuple': '''class Box:
    v = 1.0


xs = (Box,)
xs[0].v = 2.5
print(Box.v)
''',
    'negative_index': '''class Box:
    v = 1.0


xs = [Box]
xs[-1].v = 2.5
print(Box.v)
''',
    'dict': '''class Box:
    v = 1.0


d = {"c": Box}
d["c"].v = 2.5
print(Box.v)
''',
    'local_list': '''class Box:
    v = 1.0


def setv():
    xs = [Box]
    xs[0].v = 2.5


setv()
print(Box.v)
''',
}

# the default build's typed path keeps class-attribute stores that it already modelled correctly;
# the forced general build refuses them by name
TYPED = {
    'module': '''class Box:
    v = 1.0

    def __init__(self):
        self.n = 0


Box.v = 2.5
b = Box()
print(Box.v, b.v)
''',
    'method': '''class Box:
    v = 1.0

    def __init__(self):
        self.n = 0

    def bump(self):
        Box.v += 1.5


b = Box()
b.bump()
print(Box.v, b.v)
''',
    'before_and_after': '''class Box:
    v = 1.0

    def __init__(self):
        self.n = 0


b = Box()
Box.v = 2.5
c = Box()
print(b.v, c.v)
''',
}

MATCH = {
    'instance': '''class Box:
    v = 1.0


b = Box()
b.v = 3.5
print(b.v, Box.v)
''',
    'parameter_shadows_class': '''class Box:
    v = 1.0


class Other:
    v = 10.0


def setv(Box):
    Box.v = 4.5
    print(Box.v)


setv(Other())
''',
    'local_shadows_class': '''class Box:
    v = 1.0


class Other:
    v = 10.0


def setv():
    Box = Other()
    Box.v = 5.5
    print(Box.v)


setv()
''',
    'loop_target_shadows_class': '''class Box:
    v = 1.0


class Other:
    v = 10.0


for Box in (Other(),):
    Box.v = 6.5
    print(Box.v)
''',
    'closure_cell_shadows_class': '''class Box:
    v = 1.0


class Other:
    v = 10.0


def outer():
    Box = Other()

    def inner():
        Box.v = 7.5
        print(Box.v)

    inner()


outer()
''',
    'instance_alias': '''class Box:
    v = 1.0

    def __init__(self):
        self.n = 0


B = Box()
B.v = 2.5
print(B.v)
''',
    'alias_rebound_to_instance': '''class Box:
    v = 1.0


B = Box
B = Box()
B.v = 2.5
print(B.v, Box.v)
''',
    'alias_shadowed_by_local_instance': '''class Box:
    v = 1.0


B = Box


def setv():
    B = Box()
    B.v = 2.5
    print(B.v)


setv()
print(Box.v)
''',
    'value_types': '''class Box:
    i = 1
    f = 1.5
    s = "a"
    b = True
    n = -2


b1 = Box()
b1.i = -3
b1.f = 2.5
b1.s = "zz"
b1.b = False
b1.n = 0
print(b1.i, b1.f, b1.s, b1.b, b1.n, Box.i, Box.f, Box.s, Box.b, Box.n)
''',
    'mutated_container_is_an_instance': '''class Box:
    v = 1.0


xs = [Box]
ys = xs
ys[0] = Box()
xs[0].v = 2.5
print(xs[0].v, Box.v)
''',
    'empty_container_keeps_index_error': '''class Box:
    v = 1.0


xs = []
try:
    xs[0].v = 2.5
except IndexError as error:
    print("index", str(error))
print(Box.v)
''',
    'class_read_through_alias': '''class Box:
    v = 1.0

    def __init__(self):
        self.n = 0


B = Box
print(B.v)
''',
}

# the base's class-ness is not statically known (a parameter, an instance attribute): the
# compiler cannot refuse it, so the runtime names the construct instead of raising the
# misleading AttributeError
RUNTIME = {
    'parameter': '''class Box:
    v = 1.0


def setv(c):
    c.v = 2.5


setv(Box)
print(Box.v)
''',
    'attribute': '''class Holder:
    pass


class Box:
    v = 1.0


h = Holder()
h.c = Box
h.c.v = 2.5
print(Box.v)
''',
}

CLASS_STORE = 'assigning the class attribute'


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


class Pre283Tests(unittest.TestCase):
    def refused(self, slug, text):
        with tempfile.TemporaryDirectory(prefix='ail-pre283-') as directory:
            for general in (True, False):
                name = '%s_%s' % (slug, 'g' if general else 'd')
                built, exe = _build(directory, name, text, general)
                output = built.stdout + built.stderr
                self.assertNotEqual(built.returncode, 0, '%s (general=%s)\n%s' % (slug, general, output[-3000:]))
                self.assertIn(CLASS_STORE, output, '%s (general=%s)\n%s' % (slug, general, output[-3000:]))
                self.assertFalse(exe.exists(), '%s (general=%s) built an executable' % (slug, general))

    def matches(self, slug, text):
        with tempfile.TemporaryDirectory(prefix='ail-pre283-') as directory:
            want, want_rc = _cpython(directory, slug, text)
            for general in (True, False):
                name = '%s_%s' % (slug, 'g' if general else 'd')
                built, exe = _build(directory, name, text, general)
                self.assertEqual(built.returncode, 0,
                                 '%s (general=%s)\n%s' % (slug, general, (built.stdout + built.stderr)[-3000:]))
                got = subprocess.run([str(exe)], capture_output=True, timeout=120, cwd=directory)
                self.assertEqual((got.stdout.replace(b'\r\n', b'\n'), got.returncode), (want, want_rc),
                                 '%s (general=%s)' % (slug, general))

    def test_direct_class_store_refused_on_both_builds(self):
        for slug, text in DIRECT.items():
            with self.subTest(case=slug):
                self.refused(slug, text)

    def test_alias_store_refused_on_both_builds(self):
        for slug, text in ALIAS.items():
            with self.subTest(case=slug):
                self.refused(slug, text)

    def test_literal_container_store_refused_on_both_builds(self):
        for slug, text in CONTAINER.items():
            with self.subTest(case=slug):
                self.refused(slug, text)

    def test_typed_path_keeps_its_class_attribute_stores(self):
        """The default build matches CPython; the forced general build refuses by name."""
        for slug, text in TYPED.items():
            with self.subTest(case=slug), tempfile.TemporaryDirectory(prefix='ail-pre283-') as directory:
                want, want_rc = _cpython(directory, slug, text)
                built, exe = _build(directory, slug + '_d', text, general=False)
                self.assertEqual(built.returncode, 0,
                                 '%s (typed)\n%s' % (slug, (built.stdout + built.stderr)[-3000:]))
                got = subprocess.run([str(exe)], capture_output=True, timeout=120, cwd=directory)
                self.assertEqual((got.stdout.replace(b'\r\n', b'\n'), got.returncode), (want, want_rc),
                                 '%s (typed)' % slug)
                built, exe = _build(directory, slug + '_g', text, general=True)
                output = built.stdout + built.stderr
                self.assertNotEqual(built.returncode, 0, '%s (general)\n%s' % (slug, output[-3000:]))
                self.assertIn(CLASS_STORE, output, '%s (general)\n%s' % (slug, output[-3000:]))
                self.assertFalse(exe.exists(), '%s (general) built an executable' % slug)

    def test_instance_and_shadowed_stores_still_match(self):
        for slug, text in MATCH.items():
            with self.subTest(case=slug):
                self.matches(slug, text)

    def test_run_time_class_base_is_refused_by_name(self):
        for slug, text in RUNTIME.items():
            with self.subTest(case=slug), tempfile.TemporaryDirectory(prefix='ail-pre283-') as directory:
                for general in (True, False):
                    name = '%s_%s' % (slug, 'g' if general else 'd')
                    built, exe = _build(directory, name, text, general)
                    self.assertEqual(built.returncode, 0,
                                     '%s (general=%s)\n%s' % (slug, general, (built.stdout + built.stderr)[-3000:]))
                    got = subprocess.run([str(exe)], capture_output=True, timeout=120, cwd=directory)
                    error = got.stderr.decode('utf-8', 'replace')
                    self.assertNotEqual(got.returncode, 0, '%s (general=%s) ran' % (slug, general))
                    self.assertIn(CLASS_STORE, error, '%s (general=%s)\n%s' % (slug, general, error[-1500:]))


if __name__ == '__main__':
    unittest.main()
