"""pre318: reading a user method as a value is refused by name.

The pre318 review recorded four pre-existing differences where CPython makes a bound method:
a method read in a default argument, through a factory alias, through a helper parameter and
through a module alias.  The general path keeps instance fields and looks a method up only for
a call, so each program compiled and then raised ``AttributeError: 'D' object has no attribute
'g'``.  Both builds now refuse those reads by name, including the same read reached through an
argument, a list item, a dict value, an attribute, an alias, an inherited method, a classmethod
and a staticmethod.  A direct call, a property, a field of the same name, ``getattr`` and
``callable(d.g)`` keep their CPython behaviour.
"""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent
CLI = str(ROOT / 'ail_chatgpt.py')

REFUSED = {
    'default_argument': '''class D:
    def g(self):
        return 77
class C:
    def __init__(self, f):
        self.f = f
    def f(self):
        return 1
d = D()
def make(f=d.g):
    return f
print(C(make()).f())
''',
    'factory_alias': '''class D:
    def g(self):
        return 78
class C:
    def __init__(self, f):
        self.f = f
    def f(self):
        return 1
d = D()
def factory():
    return d.g
alias = factory
print(C(alias()).f())
''',
    'method_argument': '''class D:
    def g(self):
        return 80
class C:
    def __init__(self, f):
        self.f = f
    def f(self):
        return 1
d = D()
def passthrough(x):
    return x
print(C(passthrough(d.g)).f())
''',
    'global_alias': '''class D:
    def g(self):
        return 5
d = D()
g = d.g
print(g)
''',
    'argument_route': '''class D:
    def g(self):
        return 1
def call(o):
    return o.g
print(call(D()))
''',
    'list_route': '''class D:
    def g(self):
        return 2
xs = [D()]
print(xs[0].g)
''',
    'dict_route': '''class D:
    def g(self):
        return 3
dd = {"x": D()}
print(dd["x"].g)
''',
    'attribute_route': '''class D:
    def g(self):
        return 4
class Box:
    def __init__(self, d):
        self.d = d
print(Box(D()).d.g)
''',
    'alias_route': '''class D:
    def g(self):
        return 6
d = D()
alias = d
print(alias.g)
''',
    'inherited_method': '''class B:
    def g(self):
        return 7
class D(B):
    pass
print(D().g)
''',
    'classmethod_value': '''class D:
    @classmethod
    def g(cls):
        return 8
print(D().g)
''',
    'staticmethod_value': '''class D:
    @staticmethod
    def g():
        return 9
print(D().g)
''',
    'list_index_method': '''class E:
    def __init__(self):
        self.g = 5
class D:
    def g(self):
        return 1
xs = [D(), E()]
print(xs[0].g)
''',
    'list_negative_method': '''class E:
    def __init__(self):
        self.g = 5
class D:
    def g(self):
        return 1
xs = [E(), D()]
print(xs[-1].g)
''',
}

CONTROL = '''class D:
    def __init__(self):
        self.value = 3
    def g(self, x):
        return x
    @property
    def prop(self):
        return self.value
class E:
    def __init__(self):
        self.g = 42
    def g(self, x):
        return x
d = D()
print(d.g(0), d.g(-5), d.g(""), d.g([]), d.g(True), d.g(None))
print(d.prop, D().g(9223372036854775807), D().g(-9223372036854775808))
print(E().g, getattr(d, "g")(7), callable(d.g))
'''

FIELD_CONTROL = {
    'field_setattr': '''class D:
    def g(self):
        return 1
d = D()
setattr(d, 'g', 42)
print(d.g)
''',
    'field_module_assign': '''class D:
    def g(self):
        return 1
d = D()
d.g = 42
print(d.g)
''',
    'field_arg_assign': '''class D:
    def g(self):
        return 1
def setg(o):
    o.g = 42
d = D()
setg(d)
print(d.g)
''',
    'field_tuple_unpack': '''class D:
    def __init__(self, v):
        self.g, self.h = v, 2
    def g(self):
        return 1
print(D(5).g, D(5).h)
''',
    'field_nested_function': '''class D:
    def __init__(self):
        def setup(o):
            o.g = 7
        setup(self)
    def g(self):
        return 1
print(D().g)
''',
    'field_alias': '''class D:
    def g(self):
        return 1
d = D()
alias = d
alias.g = 42
print(d.g)
''',
    'field_list_item': '''class D:
    def g(self):
        return 1
d = D()
xs = [d]
xs[0].g = 42
print(d.g)
''',
    'field_dict_value': '''class D:
    def g(self):
        return 1
d = D()
dd = {'x': d}
dd['x'].g = 42
print(d.g)
''',
    'field_attribute': '''class D:
    def g(self):
        return 1
class Box:
    def __init__(self):
        self.d = D()
b = Box()
b.d.g = 42
print(b.d.g)
''',
    'list_index_field': '''class E:
    def __init__(self):
        self.g = 5
class D:
    def g(self):
        return 1
xs = [E(), D()]
print(xs[0].g, xs[-2].g)
''',
    'unbound_call_second_arg': '''class D:
    def g(self):
        return 1
    def m(self, x):
        return x.g
class E:
    def __init__(self):
        self.g = 9
print(D.m(D(), E()))
''',
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
    built = subprocess.run([sys.executable, '-B', CLI, 'compile', src.name,
                            '--syntax', 'python', '-o', exe.name], cwd=directory,
                           capture_output=True, text=True, timeout=900, env=env)
    if built.returncode != 0:
        return None, (built.stdout + built.stderr)[-3000:]
    ran = subprocess.run([str(exe)], capture_output=True, timeout=120, cwd=directory)
    return (ran.stdout.replace(b'\r\n', b'\n'), ran.returncode), ran.stderr.decode('utf-8', 'replace')[-1500:]


class Pre318Tests(unittest.TestCase):
    def check_refused(self, slug, text):
        with tempfile.TemporaryDirectory(prefix='ail-pre318-') as directory:
            for general in (True, False):
                got, build_err = _build(directory, '%s_%s' % (slug, 'g' if general else 'd'),
                                        text, general)
                self.assertIsNone(got, '%s (general=%s)\n%s' % (slug, general, build_err))
                self.assertIn('not in the subset', build_err)
                self.assertIn('bound method value', build_err)

    def test_recorded_routes_are_refused(self):
        for slug in ('default_argument', 'factory_alias', 'method_argument', 'global_alias'):
            self.check_refused(slug, REFUSED[slug])

    def test_value_routes_are_refused(self):
        for slug in ('argument_route', 'list_route', 'dict_route', 'attribute_route',
                     'alias_route', 'inherited_method', 'list_index_method',
                     'list_negative_method'):
            self.check_refused(slug, REFUSED[slug])

    def test_other_method_kinds_are_refused(self):
        for slug in ('classmethod_value', 'staticmethod_value'):
            self.check_refused(slug, REFUSED[slug])

    def test_control_keeps_cpython_behaviour(self):
        with tempfile.TemporaryDirectory(prefix='ail-pre318-') as directory:
            want, want_rc = _cpython(directory, 'control', CONTROL)
            self.assertEqual(want_rc, 0)
            for general in (True, False):
                got, build_err = _build(directory, 'control_%s' % ('g' if general else 'd'),
                                        CONTROL, general)
                self.assertIsNotNone(got, 'control (general=%s)\n%s' % (general, build_err))
                self.assertEqual(got, (want, want_rc), 'control (general=%s)\n%s'
                                 % (general, build_err))

    def test_field_routes_keep_cpython_behaviour(self):
        for slug, text in FIELD_CONTROL.items():
            with tempfile.TemporaryDirectory(prefix='ail-pre318-') as directory:
                want, want_rc = _cpython(directory, slug, text)
                self.assertEqual(want_rc, 0, slug)
                for general in (True, False):
                    got, build_err = _build(directory, '%s_%s' % (slug, 'g' if general else 'd'),
                                            text, general)
                    self.assertIsNotNone(got, '%s (general=%s)\n%s'
                                         % (slug, general, build_err))
                    self.assertEqual(got, (want, want_rc), '%s (general=%s)\n%s'
                                     % (slug, general, build_err))


if __name__ == '__main__':
    unittest.main()
