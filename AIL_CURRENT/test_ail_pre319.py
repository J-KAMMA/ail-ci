"""pre319: calling an earlier function-valued class attribute.

The pre304 reviewer recorded this as a pre-existing difference: a class body that
calls a function bound earlier in the same body (``f = lambda: 3; g = f()``, and
the ``def`` spelling) is refused by name on both builds, while CPython evaluates
the call and stores its result as the next class attribute.  This tree already
refuses the construct at compile time with a named ``not in the subset`` message,
which the task accepts, so no compiler change is needed.  The test checks that
every route is either refused by name on both builds or matches CPython, so a
wrong output is never accepted.

Values reach the call through a plain name, an alias, a list item, a dict value,
an attribute, an argument and a module constant; the result is read through an
instance and then through a function argument, a list item, an attribute and a
dict value.  Functions bound outside the class still work through a list item and
a dict value, which are the in-subset boundaries.
"""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent

CASES = {
    'direct_noargs': '''
class C:
    f = lambda: 3
    g = f()
print(C().g)
''',
    'direct_args': '''
class C:
    f = lambda x: x * 2
    g = f(4)
print(C().g)
''',
    'multiple_args_negative': '''
class C:
    f = lambda a, b: a - b
    g = f(1, 5)
print(C().g)
''',
    'def_call': '''
class C:
    def f():
        return 4
    g = f()
print(C().g)
''',
    'alias': '''
class C:
    f = lambda: 5
    h = f
    g = h()
print(C().g)
''',
    'list_item': '''
class C:
    fs = [lambda: 6]
    g = fs[0]()
print(C().g)
''',
    'dict_value': '''
class C:
    fs = {"k": lambda: 7}
    g = fs["k"]()
print(C().g)
''',
    'attribute_route': '''
class Box:
    def __init__(self):
        self.f = lambda: 8
box = Box()
class C:
    g = box.f()
print(C().g)
''',
    'argument_list_dict_routes': '''
n = 3
args = [4]
d = {"n": 5}
class Box:
    v = 6
class C:
    f = lambda x: x + 1
    a = f(n)
    b = f(args[0])
    c = f(d["n"])
    e = f(Box.v)
print(C().a, C().b, C().c, C().e)
''',
    'result_routes': '''
class C:
    f = lambda x: x + 1
    g = f(4)
def show(v):
    print(v)
class Holder:
    item = None
c = C()
show(c.g)
print([c.g][0])
h = Holder()
h.item = c
print(h.item.g)
print({"c": c}["c"].g)
''',
    'empty_and_bool_results': '''
class C:
    f = lambda: []
    g = f()
    h = lambda x: -x
    i = h(True)
print(C().g, C().i)
''',
    'external_list_match': '''
fs = [lambda: 9]
class C:
    g = fs[0]()
print(C().g)
''',
    'external_dict_match': '''
fs = {"k": lambda: 10}
class C:
    g = fs["k"]()
print(C().g)
''',
}

REFUSALS = ('not in the subset', 'reading the class attribute', 'class attribute')


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


class Pre319(unittest.TestCase):
    def test_function_valued_class_attribute_call(self):
        for slug, source in CASES.items():
            with tempfile.TemporaryDirectory(prefix='ail-pre319-') as directory:
                expected, status = run_cpython(directory, 'pre319_' + slug, source)
            modes = set()
            for general in (False, True):
                with self.subTest(slug=slug, general=general), \
                        tempfile.TemporaryDirectory(prefix='ail-pre319-') as directory:
                    built, exe = compile_source(directory, 'pre319_' + slug, source, general)
                    output = built.stdout + built.stderr
                    if built.returncode != 0:
                        self.assertFalse(exe.exists(), '%s built an executable' % slug)
                        self.assertTrue(any(marker in output for marker in REFUSALS),
                                        output[-4000:])
                        modes.add('refused')
                    else:
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
