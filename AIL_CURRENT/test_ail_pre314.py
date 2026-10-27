"""pre314: a field holding a bound method is refused by name, not miscompiled.

The rbpre278 review recorded this as already present before that job: a class that defines a
method ``f`` and also stores a bound method in an instance field ``f`` compiled, then stopped
with ``AttributeError: '<class>' object has no attribute '<method>'``.  CPython calls the stored
bound method (the instance table wins over the class's non-data method descriptor).  The
instance-table route handles plain functions, classes and ``__call__`` instances, but it has no
route for a bound method, so such a call is refused by name at compile time on both builds.
The bound method reaches the field directly, through an argument/default, a list item, a dict
value, an attribute or an alias; a base method's ``self.f()`` is refused when a constructed
subclass stores a bound method.  Fields holding lambdas/functions still match CPython (including
through a base method), and a receiver that is never constructed, a subclass that overrides
``__init__`` without storing the field, and an unrelated local or stale annotation are not caught
by a collision elsewhere.
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
    'self_bound': '''class C:
    def __init__(self):
        self.f = self.g
    def g(self):
        return 55
    def f(self):
        return 102
print(C().f())
''',
    'other_object': '''class D:
    def g(self):
        return 77
class C:
    def __init__(self):
        d = D()
        self.f = d.g
    def f(self):
        return 102
print(C().f())
''',
    'builtin_method': '''class C:
    def __init__(self):
        self.f = [1, 2, 3].append
    def f(self):
        return 102
print(C().f(9))
''',
    'constructor_argument': '''class D:
    def g(self):
        return 80
class C:
    def __init__(self, h):
        self.f = h
    def f(self):
        return 102
d = D()
print(C(d.g).f())
''',
    'default_argument': '''class D:
    def g(self):
        return 77
class C:
    def __init__(self, h=None):
        self.f = h
    def f(self):
        return 102
d = D()
print(C(d.g).f())
''',
    'list_item': '''class D:
    def g(self):
        return 81
class C:
    def __init__(self):
        xs = [D().g]
        self.f = xs[0]
    def f(self):
        return 102
print(C().f())
''',
    'dict_value': '''class D:
    def g(self):
        return 82
class C:
    def __init__(self):
        d = {"g": D().g}
        self.f = d["g"]
    def f(self):
        return 102
print(C().f())
''',
    'attribute': '''class D:
    def g(self):
        return 83
class Box:
    def __init__(self):
        self.h = D().g
class C:
    def __init__(self):
        self.f = Box().h
    def f(self):
        return 102
print(C().f())
''',
    'alias': '''class D:
    def g(self):
        return 84
class C:
    def __init__(self):
        m = D().g
        self.f = m
    def f(self):
        return 102
print(C().f())
''',
    'base_method_bound_field': '''class B:
    def run(self):
        return self.f()
    def f(self):
        return 100
class C(B):
    def __init__(self):
        self.f = self.g
    def g(self):
        return 5
print(C().run())
''',
    'super_init_bound_field': '''class C:
    def __init__(self):
        self.f = self.g
    def g(self):
        return 5
    def f(self):
        return 100
class D(C):
    def __init__(self):
        super().__init__()
print(D().f())
''',
}

MATCH = {
    'lambda_field': '''class C:
    def __init__(self):
        self.f = lambda x: x + 100
    def f(self, x):
        return x + 101
c = C()
print(c.f(1), c.f(2))
''',
    'function_field': '''def plus(x):
    return x + 7
class C:
    def __init__(self):
        self.f = plus
    def f(self, x):
        return x + 101
print(C().f(1))
''',
    'unrelated_scope': '''class C:
    def __init__(self):
        self.f = lambda: 101
    def f(self):
        return 102
class D:
    def f(self):
        return 7
def a():
    x = C()
def b():
    x = D()
    return x.f()
print(b())
''',
    'collision_without_call': '''class C:
    def __init__(self):
        self.f = lambda x: x + 1
    def f(self, x):
        return x + 2
print(C().__class__.__name__)
''',
    'noncallable_field': '''class C:
    def __init__(self, v):
        self.f = v
    def f(self, x):
        return x + 100
for v in (None, True, -1, "", [], 2.5):
    try:
        C(v).f(1)
    except TypeError as e:
        print(e)
''',
    'plain_program': '''class C:
    def __init__(self, x):
        self.x = x
    def twice(self):
        return self.x * 2
print(C(21).twice())
''',
    # A base method's ``self.f()`` with a lambda field stored by a subclass: the pre279
    # instance-table route handles it, so this must not be refused (review defect 2).
    'base_method_subclass_lambda': '''class B:
    def run(self):
        return self.f()
    def f(self):
        return 100
class C(B):
    def __init__(self):
        self.f = lambda: 5
print(C().run(), B().run())
''',
    # Only D (which overrides f and does not store the field) is constructed; C stores a bound
    # method but never runs (review defect 1).
    'sibling_only': '''class B:
    def run(self):
        return self.f()
class C(B):
    def __init__(self):
        self.f = self.g
    def g(self):
        return 5
    def f(self):
        return 100
class D(B):
    def f(self):
        return 7
print(D().run())
''',
    # D overrides __init__ without storing the field, so it inherits no field from C.
    'sub_overrides': '''class C:
    def __init__(self):
        self.f = self.g
    def g(self):
        return 55
    def f(self):
        return 102
class D(C):
    def __init__(self):
        pass
    def f(self):
        return 7
print(D().f())
''',
    # The annotation is stale; the value actually iterated is a D.
    'for_annot': '''class C:
    def __init__(self):
        self.f = self.g
    def g(self):
        return 55
    def f(self):
        return 102
class D:
    def f(self):
        return 7
x: C
for x in [D()]:
    print(x.f())
''',
    'base_method_subclass_function': '''def five():
    return 5
class B:
    def run(self):
        return self.f()
    def f(self):
        return 100
class C(B):
    def __init__(self):
        self.f = five
print(C().run(), B().run())
''',
    'super_init_lambda': '''class C:
    def __init__(self):
        self.f = lambda: 5
    def f(self):
        return 100
class D(C):
    def __init__(self):
        super().__init__()
print(D().f(), C().f())
''',
    'super_init_override': '''class C:
    def __init__(self):
        self.f = self.g
    def g(self):
        return 5
    def f(self):
        return 100
class D(C):
    def __init__(self):
        self.x = 1
print(D().f())
''',
}


def _build(directory, name, text, general):
    src = Path(directory) / (name + '.py')
    exe = Path(directory) / (name + ('_g' if general else '_d'))
    src.write_text(text, encoding='utf-8')
    env = dict(os.environ, AIL_NO_CACHE='1', AIL_QUIET_FALLBACK='1')
    env.pop('AIL_NO_GENERAL', None)
    env.pop('AIL_GENERAL', None)
    if general:
        env['AIL_UNIFIED_FORCE'] = '1'
    else:
        env.pop('AIL_UNIFIED_FORCE', None)
    built = subprocess.run([sys.executable, '-B', CLI, 'compile', src.name,
                            '--syntax', 'python', '-o', exe.name], cwd=directory,
                           capture_output=True, text=True, timeout=900, env=env)
    if built.returncode != 0:
        return None, built.stdout + built.stderr
    ran = subprocess.run([str(exe)], cwd=directory, capture_output=True, timeout=120)
    return (ran.stdout.replace(b'\r\n', b'\n'), ran.returncode), ran.stderr.decode('utf-8', 'replace')


class Pre314(unittest.TestCase):
    def test_bound_method_field_is_refused_by_name(self):
        with tempfile.TemporaryDirectory(prefix='ail-pre314-') as directory:
            for slug, text in REFUSED.items():
                for general in (False, True):
                    with self.subTest(case=slug, general=general):
                        got, output = _build(directory, '%s_%s' % (slug, 'g' if general else 'd'),
                                             text, general)
                        self.assertIsNone(got, output)
                        self.assertIn('not in the subset', output)
                        self.assertIn('also stores an instance field named f', output)
                        self.assertNotIn('Traceback', output)
                        self.assertNotIn('AttributeError', output)

    def test_supported_fields_and_unrelated_receivers_still_match_cpython(self):
        with tempfile.TemporaryDirectory(prefix='ail-pre314-') as directory:
            for slug, text in MATCH.items():
                want = subprocess.run([sys.executable, '-B', '-c', text], capture_output=True,
                                      timeout=120, env=dict(os.environ, PYTHONUTF8='1'))
                self.assertEqual(want.returncode, 0, want.stderr)
                expected = want.stdout.replace(b'\r\n', b'\n')
                for general in (False, True):
                    with self.subTest(case=slug, general=general):
                        got, output = _build(directory, '%s_%s' % (slug, 'g' if general else 'd'),
                                             text, general)
                        self.assertIsNotNone(got, output)
                        self.assertEqual(got, (expected, 0), output)


if __name__ == '__main__':
    unittest.main()
