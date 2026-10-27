# -*- coding: utf-8 -*-
"""pre344: a write through the dict ``vars()`` returns is refused by name.

The pre318 reviewer recorded as pre-existing that ``vars(d)['g'] = 5`` then ``print(d.g)``
raised ``AttributeError`` on both builds where CPython updates the instance's live ``__dict__``
and prints ``5``.  The general path hands out a copy, so this front-end pass tracks a ``vars()``
result through aliases, displays, attributes, loop/with targets, arguments and returns, and
refuses the first write through it (item store/delete/augmented store, ``update``,
``setdefault``, ``pop``, ``popitem``, ``clear``).  Read-only uses keep matching CPython.
"""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REFUSAL = 'mutating the dict returned by vars() is not in the subset'

CASES = {
    'direct_item_store': ('''
class D:
    def g(self):
        return 1
d = D()
vars(d)['g'] = 5
print(d.g)
''', 'refused'),
    'alias_item_store': ('''
class D:
    def g(self):
        return 1
d = D()
v = vars(d)
v['g'] = 6
print(d.g)
''', 'refused'),
    'argument_item_store': ('''
class D:
    def g(self):
        return 1
def setg(v):
    v['g'] = 7
d = D()
setg(vars(d))
print(d.g)
''', 'refused'),
    'argument_alias': ('''
class D:
    def g(self):
        return 1
def setg(v):
    w = v
    w['g'] = 8
d = D()
v = vars(d)
setg(v)
print(d.g)
''', 'refused'),
    'callee_own_vars': ('''
class D:
    def g(self):
        return 1
def setg(o):
    vars(o)['g'] = 9
d = D()
setg(d)
print(d.g)
''', 'refused'),
    'list_item_route': ('''
class D:
    def g(self):
        return 1
d = D()
xs = [vars(d)]
xs[0]['g'] = 10
print(d.g)
''', 'refused'),
    'attribute_route': ('''
class D:
    def g(self):
        return 1
class H:
    pass
d = D()
h = H()
h.v = vars(d)
h.v['g'] = 11
print(d.g)
''', 'refused'),
    'dict_value_route': ('''
class D:
    def g(self):
        return 1
d = D()
dd = {'v': vars(d)}
dd['v']['g'] = 12
print(d.g)
''', 'refused'),
    'attribute_name_collision': ('''
class D:
    pass
class H:
    pass
d = D()
d.a = 1
h = H()
h.v = vars(d)
h2 = H()
h2.v = {'x': 1}
h2.v['y'] = 2
print(sorted(h2.v.items()))
''', 'ran'),
    'nested_attribute_collision': ('''
class D:
    pass
class Box:
    pass
class H:
    pass
d = D()
d.a = 1
a = Box()
b = Box()
a.h = H()
a.h.v = vars(d)
b.h = H()
b.h.v = {'x': 1}
b.h.v['y'] = 2
print(sorted(b.h.v.items()))
''', 'ran'),
    'subscript_attribute_collision': ('''
class D:
    pass
class H:
    pass
d = D()
d.a = 1
xs = [H(), H()]
xs[0].v = vars(d)
xs[1].v = {'x': 1}
xs[1].v['y'] = 2
print(sorted(xs[1].v.items()))
''', 'ran'),
    'scope_attribute_collision': ('''
class D:
    pass
class H1:
    pass
class H2:
    pass
d = D()
d.a = 1
def tainted():
    h = H1()
    h.v = vars(d)
    return sorted(h.v.items())
def plain():
    h = H2()
    h.v = {'x': 1}
    h.v['y'] = 2
    return sorted(h.v.items())
print(tainted(), plain())
''', 'ran'),
    'rebind_plain_dict': ('''
class D:
    pass
d = D()
d.a = 1
v = vars(d)
v = {'x': 1}
v['y'] = 2
print(sorted(v.items()))
''', 'ran'),
    'rebind_after_mutation': ('''
class D:
    pass
d = D()
d.a = 1
v = vars(d)
v['a'] = 5
v = {'x': 1}
print(sorted(v.items()))
''', 'refused'),
    'vars_of_list_item': ('''
class D:
    def g(self):
        return 1
d = D()
xs = [d]
vars(xs[0])['g'] = 13
print(d.g)
''', 'refused'),
    'vars_of_attribute': ('''
class D:
    def g(self):
        return 1
class H:
    pass
d = D()
h = H()
h.d = d
vars(h.d)['g'] = 14
print(d.g)
''', 'refused'),
    'vars_of_dict_value': ('''
class D:
    def g(self):
        return 1
d = D()
dd = {'d': d}
vars(dd['d'])['g'] = 15
print(d.g)
''', 'refused'),
    'method_update': ('''
class D:
    def g(self):
        return 1
d = D()
vars(d).update({'g': 16})
print(d.g)
''', 'refused'),
    'method_setdefault': ('''
class D:
    def g(self):
        return 1
d = D()
vars(d).setdefault('g', 17)
print(d.g)
''', 'refused'),
    'method_pop': ('''
class D:
    def __init__(self):
        self.x = 1
d = D()
vars(d).pop('x')
print(vars(d))
''', 'refused'),
    'method_clear': ('''
class D:
    def __init__(self):
        self.x = 1
d = D()
vars(d).clear()
print(vars(d))
''', 'refused'),
    'item_delete': ('''
class D:
    def g(self):
        return 1
d = D()
vars(d)['g'] = 18
del vars(d)['g']
print(d.g)
''', 'refused'),
    'item_augassign': ('''
class D:
    def __init__(self):
        self.x = 1
d = D()
vars(d)['x'] += 1
print(d.x)
''', 'refused'),
    'transitive_argument': ('''
class D:
    def g(self):
        return 1
def inner(v):
    v['g'] = 19
def outer(v):
    inner(v)
d = D()
outer(vars(d))
print(d.g)
''', 'refused'),
    'returned_vars': ('''
class D:
    def g(self):
        return 1
def getv(o):
    return vars(o)
d = D()
v = getv(d)
v['g'] = 20
print(d.g)
''', 'refused'),
    'returned_list_of_vars': ('''
class D:
    def g(self):
        return 1
def wrap(o):
    return [vars(o)]
d = D()
xs = wrap(d)
xs[0]['g'] = 21
print(d.g)
''', 'refused'),
    'values_loop_mutation': ('''
class D:
    def g(self):
        return 1
d = D()
dd = {'a': vars(d)}
for v in dd.values():
    v['g'] = 22
print(d.g)
''', 'refused'),
    'items_loop_mutation': ('''
class D:
    def g(self):
        return 1
d = D()
dd = {'a': vars(d)}
for k, v in dd.items():
    v['g'] = 23
print(d.g)
''', 'refused'),
    'tuple_unpack_route': ('''
class D:
    def g(self):
        return 1
d = D()
v, n = vars(d), 0
v['g'] = 24
print(d.g)
''', 'refused'),
    'star_unpack_route': ('''
class D:
    def g(self):
        return 1
d = D()
first, *rest = [vars(d), 1]
first['g'] = 25
print(d.g)
''', 'refused'),
    'comprehension_mutation': ('''
class D:
    def g(self):
        return 1
d = D()
dd = {'a': vars(d)}
[v.update({'g': 26}) for v in dd.values()]
print(d.g)
''', 'refused'),
    'read_only_values_loop': ('''
class D:
    def __init__(self):
        self.x = 1
d = D()
dd = {'a': vars(d)}
for v in dd.values():
    print(v['x'])
''', 'ran'),
    'read_only_vars': ('''
class D:
    def __init__(self):
        self.x = 1
        self.y = 2
d = D()
v = vars(d)
print(v['x'], sorted(v), vars(d))
''', 'ran'),
    'read_only_argument': ('''
class D:
    def __init__(self):
        self.x = 1
def show(v):
    return v['x']
d = D()
print(show(vars(d)))
''', 'ran'),
    'read_only_return': ('''
class D:
    def __init__(self):
        self.x = 1
def getv(o):
    return vars(o)
d = D()
print(getv(d)['x'])
''', 'ran'),
    'unrelated_same_name_local': ('''
class D:
    def __init__(self):
        self.x = 1
d = D()
v = vars(d)
def f():
    v = [1]
    v.append(2)
    return v
print(f(), v['x'])
''', 'ran'),
    'plain_dict_mutation': ('''
d = {'x': 1}
v = d
v['x'] = 2
v.update({'y': 3})
print(d)
''', 'ran'),
    'nested_container_not_mutated': ('''
class D:
    def __init__(self):
        self.x = 1
d = D()
xs = [[vars(d)]]
xs[0][0] = {}
print(xs, d.x)
''', 'ran'),
}


def compile_source(directory, name, source, general):
    path = Path(directory) / (name + '.ail')
    path.write_text(source, encoding='utf-8')
    env = dict(os.environ, AIL_NO_CACHE='1', AIL_QUIET_FALLBACK='1')
    env.pop('AIL_UNIFIED_FORCE', None)
    if general:
        env['AIL_UNIFIED_FORCE'] = '1'
    exe = Path(directory) / (name + ('_g' if general else '_d'))
    built = subprocess.run([sys.executable, '-B', str(ROOT / 'ail_chatgpt.py'), 'compile', path.name,
                            '--syntax', 'python', '-o', exe.name], cwd=directory,
                           capture_output=True, text=True, timeout=900, env=env)
    return built, exe


def run_cpython(directory, name, source):
    path = Path(directory) / (name + '_cpython.py')
    path.write_text(source, encoding='utf-8')
    ran = subprocess.run([sys.executable, '-B', path.name], cwd=directory, capture_output=True,
                         text=True, timeout=120)
    return ran.stdout.replace('\r\n', '\n'), ran.returncode


class Pre344(unittest.TestCase):
    def test_vars_result_mutation(self):
        for slug, (source, expected_mode) in CASES.items():
            with tempfile.TemporaryDirectory(prefix='ail-pre344-') as directory:
                expected, status = run_cpython(directory, 'pre344_' + slug, source)
            modes = set()
            for general in (False, True):
                with self.subTest(slug=slug, general=general), \
                        tempfile.TemporaryDirectory(prefix='ail-pre344-') as directory:
                    built, exe = compile_source(directory, 'pre344_' + slug, source, general)
                    output = built.stdout + built.stderr
                    if expected_mode == 'refused':
                        self.assertNotEqual(built.returncode, 0, '%s built' % slug)
                        self.assertFalse(exe.exists(), '%s built an executable' % slug)
                        self.assertIn(REFUSAL, output, output[-4000:])
                        modes.add('refused')
                    else:
                        self.assertEqual(built.returncode, 0, output[-4000:])
                        self.assertTrue(exe.exists(), '%s did not build' % slug)
                        ran = subprocess.run([str(exe)], cwd=directory, capture_output=True,
                                             text=True, timeout=120)
                        self.assertEqual(ran.returncode, status, ran.stdout + ran.stderr)
                        self.assertEqual(ran.stdout.replace('\r\n', '\n'), expected,
                                         ran.stdout + ran.stderr)
                        modes.add('ran')
            self.assertEqual(len(modes), 1, '%s builds disagree: %s' % (slug, sorted(modes)))


if __name__ == '__main__':
    unittest.main()
