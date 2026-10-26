"""pre304: a class body's earlier names are visible to its later attributes.

The rbrbfuzz28 reviewer recorded this pre-existing difference: a class-body comprehension that
reads an earlier class attribute in its outermost iterable (``class C: x = 3; ys = [i for i in
range(x)]``) compiled and then stopped with ``name 'x' is not defined``, both when ``ys`` was read
through an instance and when it was read through ``C()``.  CPython runs the class body in its own
namespace, so ``x`` is visible there; inherited attributes and an empty comprehension had the
same refusal.

The general path now keeps the class body's earlier assignments in a temporary name map while
it compiles each attribute value.  For a comprehension only the outermost iterable sees that map,
as in CPython: the body of a comprehension runs in its own scope, so a class name there still
falls back to a module global of the same name (or is refused by name when there is none).
Values reach the later attribute through a plain name, arithmetic, an alias, a list item, a dict
value and an instance attribute; the instance is then used through a function argument, a list
item, an attribute and a dict value.  Programs are built with the general path forced and with
the default build; stdout and the exit status must match CPython.
"""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent

PROGRAMS = {
    'instance': '''
class C:
    x = 3
    ys = [i for i in range(x)]
o = C()
print(o.ys, o.x)
''',
    'call': '''
class C:
    x = 3
    ys = [i for i in range(x)]
print(C().ys, C().x)
''',
    'inherited': '''
class B:
    x = 3
    ys = [i for i in range(x)]
class D(B):
    pass
o = D()
print(o.ys, o.x)
''',
    'empty': '''
class C:
    x = 3
    ys = [i for i in range(0)]
o = C()
print(o.ys, o.x)
''',
    'comprehensions': '''
class C:
    x = 3
    a = [i for i in range(x)]
    b = {i for i in range(x)}
    c = {i: i * i for i in range(x)}
    d = list(i for i in range(x))
o = C()
print(o.a, sorted(o.b), o.c, o.d, o.x)
''',
    'routes': '''
holder = [5]
d = {"n": 4}
class Box:
    v = 2
class C:
    x = holder[0]
    y = d["n"]
    z = Box().v
    a = [i for i in range(x)]
    b = [i for i in range(y)]
    c = [i for i in range(z)]
o = C()
print(o.a, o.b, o.c, o.x, o.y, o.z)
''',
    'argument_and_containers': '''
class C:
    x = 3
    ys = [i for i in range(x)]
class Holder:
    item = None
def show(c):
    print(c.ys, c.x)
def via_list(cs):
    print(cs[0].ys)
def via_attr(h):
    print(h.item.ys)
def via_dict(d):
    print(d["c"].ys)
c = C()
show(c)
via_list([c])
h = Holder()
h.item = c
via_attr(h)
via_dict({"c": c})
''',
    'shadowed_global': '''
x = 10
class C:
    x = 3
    ys = [i for i in range(x)]
o = C()
print(o.ys, o.x, x)
''',
    'comprehension_body_global': '''
x = 2
class C:
    x = 3
    ys = [i for i in range(3) if i < x]
o = C()
print(o.ys, o.x, x)
''',
    'arithmetic': '''
class C:
    x = 3
    y = x + 1
    z = x * 2
    big = 10 ** 12
    bigger = big * 9
o = C()
print(o.x, o.y, o.z, o.big, o.bigger)
''',
    'duplicate_and_later': '''
x = 10
class C:
    a = [i for i in range(x)]
    x = 3
    x = x + 1
    b = [i for i in range(x)]
o = C()
print(o.a, o.b, o.x, x)
''',
    'negative_bool_zero': '''
class C:
    x = -3
    ys = [i for i in range(x)]
class D:
    x = True
    ys = [i for i in range(x)]
class E:
    x = 0
    ys = [i for i in range(x)]
print(C().ys, C().x)
print(D().ys, D().x)
print(E().ys, E().x)
''',
    'override': '''
class B:
    x = 3
    ys = [i for i in range(x)]
class D(B):
    x = 10
    zs = [i for i in range(x)]
o = D()
print(o.ys, o.zs, o.x)
''',
    'class_and_method_read': '''
class C:
    x = 3
    ys = [i for i in range(x)]
    def total(self):
        return len(self.ys) + self.x
o = C()
print(C.x, C.ys)
print(o.total(), o.ys)
''',
    'method_then_attribute': '''
class C:
    def x(self):
        return 9
    x = 3
    y = x + 1
print(C().x, C().y)
''',
    'attribute_then_method_then_attribute': '''
class C:
    x = 3
    def x(self):
        return 9
    x = 5
    y = x + 1
print(C().x, C().y)
''',
}

# A method or property rebinds an earlier class attribute to a function in the class namespace.
# The name map cannot hold a function value, so a later attribute that reads the name must be
# refused by name at compile time (the base behaviour) rather than reading the stale attribute.
METHOD_SHADOWS = {
    'method_shadows_attribute': '''
class C:
    x = 3
    def x(self):
        return 9
    y = x + 1
print(C().y)
''',
    'method_shadows_attribute_comprehension': '''
class C:
    x = 3
    def x(self):
        return 9
    ys = [i for i in range(x)]
print(C().ys)
''',
    'property_shadows_attribute': '''
class C:
    x = 3
    @property
    def x(self):
        return 9
    y = x + 1
print(C().y)
''',
    'method_shadows_attribute_over_global': '''
x = 100
class C:
    x = 3
    def x(self):
        return 9
    y = x + 1
print(C().y)
''',
}

COMPREHENSION_BODY = '''
class C:
    x = 3
    ys = [i for i in range(3) if i < x]
o = C()
print(o.ys)
'''


def _run_cpython(directory, name, text):
    source = Path(directory) / (name + '_cpython.py')
    source.write_text(text, encoding='utf-8')
    done = subprocess.run([sys.executable, '-B', str(source)], capture_output=True, timeout=120,
                          env=dict(os.environ, PYTHONUTF8='1'))
    return done.stdout.replace(b'\r\n', b'\n'), done.returncode


def _build(directory, name, text, general):
    source = Path(directory) / (name + '.py')
    source.write_text(text, encoding='utf-8')
    exe = Path(directory) / ('exe_' + name + ('_g' if general else '_d'))
    env = dict(os.environ, AIL_NO_CACHE='1', AIL_QUIET_FALLBACK='1')
    env.pop('AIL_NO_GENERAL', None)
    if general:
        env['AIL_UNIFIED_FORCE'] = '1'
    else:
        env.pop('AIL_UNIFIED_FORCE', None)
    return exe, subprocess.run([sys.executable, '-B', str(ROOT / 'ail_chatgpt.py'), 'compile',
                                source.name, '--syntax', 'python', '-o', exe.name], cwd=directory,
                               capture_output=True, text=True, timeout=1200, env=env)


def _build_and_run(directory, name, text, general):
    exe, built = _build(directory, name, text, general)
    if built.returncode != 0:
        return None, (built.stdout + built.stderr)[-3000:]
    got = subprocess.run([str(exe)], capture_output=True, timeout=120, cwd=directory)
    return ((got.stdout.replace(b'\r\n', b'\n'), got.returncode),
            got.stderr.decode('utf-8', 'replace')[-1500:])


class Pre304Tests(unittest.TestCase):
    def test_class_body_earlier_name_matches_cpython(self):
        with tempfile.TemporaryDirectory(prefix='ail-pre304-') as directory:
            for slug, text in PROGRAMS.items():
                want = _run_cpython(directory, slug, text)
                for general in (True, False):
                    got, build_err = _build_and_run(
                        directory, '%s_%s' % (slug, 'g' if general else 'd'), text, general)
                    self.assertIsNotNone(got, '%s (general=%s)\n%s' % (slug, general, build_err))
                    self.assertEqual(got, want, '%s (general=%s)\n%s' % (slug, general, build_err))

    def test_comprehension_body_class_name_is_refused_by_name(self):
        with tempfile.TemporaryDirectory(prefix='ail-pre304-') as directory:
            self.assertEqual(_run_cpython(directory, 'body', COMPREHENSION_BODY)[1], 1)
            for general in (True, False):
                _, built = _build(directory, 'body_%s' % ('g' if general else 'd'),
                                  COMPREHENSION_BODY, general)
                self.assertNotEqual(built.returncode, 0, built.stdout + built.stderr)
                self.assertIn("name 'x' is not defined", built.stdout + built.stderr)

    def test_method_rebinding_an_earlier_attribute_is_refused_by_name(self):
        with tempfile.TemporaryDirectory(prefix='ail-pre304-') as directory:
            for slug, text in METHOD_SHADOWS.items():
                self.assertNotEqual(_run_cpython(directory, slug, text)[1], 0, slug)
                for general in (True, False):
                    _, built = _build(directory, '%s_%s' % (slug, 'g' if general else 'd'),
                                      text, general)
                    self.assertNotEqual(built.returncode, 0, slug + '\n' + built.stdout + built.stderr)
                    self.assertIn("name 'x' is not defined", built.stdout + built.stderr)


if __name__ == '__main__':
    unittest.main()
