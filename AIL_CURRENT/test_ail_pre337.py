"""Pre337: int() of an out-of-int64 float read through a function parameter's item.

The rbrbpre31 review recorded as pre-existing that ``int(items[0])`` with ``items`` a parameter
compiled and then stopped with ``integer overflow``, where CPython prints the exact big integer.
The front end now follows a parameter subscript (and a short wrapper chain) back to a statically
known argument and refuses the conversion by name when the item is a float outside int64.  In-range
items, a rebound parameter or index, a mutated container and a locally shadowed ``int`` stay on
CPython's behaviour.
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


def check_refused(test, name, text):
    with tempfile.TemporaryDirectory(prefix='ail-pre337-') as directory:
        for general in (True, False):
            _, built = build(directory, name + ('g' if general else 'd'), text, general)
            test.assertNotEqual(built.returncode, 0, (name, general))
            message = built.stdout + built.stderr
            test.assertIn('int() of a float outside int64', message, (name, general, message[-1200:]))
            test.assertIn('big integer', message, (name, general, message[-1200:]))


def check_program(test, name, text):
    with tempfile.TemporaryDirectory(prefix='ail-pre337-') as directory:
        want = cpython(directory, name, text)
        for general in (True, False):
            exe, built = build(directory, name, text, general)
            test.assertEqual(built.returncode, 0, built.stdout + built.stderr)
            got = subprocess.run([str(exe)], capture_output=True, timeout=120, cwd=directory)
            test.assertEqual(got.stdout.replace(b'\r\n', b'\n'), want[0], (name, general, got.stderr[-800:]))
            test.assertEqual(got.returncode, want[1], (name, general, got.stderr[-800:]))


REFUSED = {
    'parameter_item': '''
def f(items):
    return int(items[0])


print(f([1e300]))
''',
    'parameter_dict_value': '''
def f(items):
    return int(items["v"])


print(f({"v": 1e300}))
''',
    'parameter_negative': '''
def f(items):
    return int(items[-1])


print(f([1.5, 1e300]))
''',
    'parameter_index_parameter': '''
def f(items, i):
    return int(items[i])


print(f([1e300], 0))
''',
    'parameter_wrapper': '''
def take(items):
    return int(items[0])


def outer(y):
    return take(y)


print(outer([1e300]))
''',
    'parameter_module_container': '''
a = [1e300]


def f(items):
    return int(items[0])


print(f(a))
''',
    'parameter_module_alias': '''
a = [1e300]
b = a


def f(items):
    return int(items[0])


print(f(b))
''',
    'parameter_attribute': '''
class Box:
    items = [1e300]


def f(items):
    return int(items[0])


print(f(Box.items))
''',
    'parameter_dict_value_route': '''
d = {"v": [1e300]}


def f(items):
    return int(items[0])


print(f(d["v"]))
''',
    'parameter_list_item_route': '''
def f(items):
    return int(items[0])


print(f([[1e300]][0]))
''',
    'parameter_keyword': '''
def f(items):
    return int(items[0])


print(f(items=[1e300]))
''',
    'parameter_nested_item': '''
def f(items):
    return int(items[0][0])


print(f([[1e300]]))
''',
    'parameter_upper_bound': '''
def f(items):
    return int(items[0])


print(f([1e19]))
''',
    'parameter_literal_call_in_function': '''
def f(items):
    return int(items[0])


def g():
    return f([1e300])


print(g())
''',
}

MATCH = {
    'in_range': '''
def f(items):
    return int(items[0])


print(f([1.9]), f([-1.9]), f([0.0]), f([9.0e18]))
''',
    'non_float_items': '''
def f(items):
    return int(items[0])


print(f([10]), f([True]))
''',
    'rebound_parameter': '''
def f(items):
    items = [1.5]
    return int(items[0])


print(f([1e300]))
''',
    'rebound_index': '''
def f(items, i):
    i = 1
    return int(items[i])


print(f([1e300, 1.5], 0))
''',
    'mutated_container': '''
a = [1e300]
a[0] = 1.5


def f(items):
    return int(items[0])


print(f(a))
''',
    'mutated_via_call': '''
def bump(xs):
    xs[0] = 1.5


a = [1e300]
bump(a)


def f(items):
    return int(items[0])


print(f(a))
''',
    'mutated_via_method_call': '''
def bump(xs):
    xs.clear()
    xs.append(1.5)


a = [1e300]
bump(a)


def f(items):
    return int(items[0])


print(f(a))
''',
    'mutated_via_keyword_call': '''
def bump(xs):
    xs[0] = 1.5


a = [1e300]
bump(xs=a)


def f(items):
    return int(items[0])


print(f(a))
''',
    'mutated_via_wrapper_call': '''
def setx(xs):
    xs[0] = 1.5


def bump(ys):
    setx(ys)


a = [1e300]
bump(a)


def f(items):
    return int(items[0])


print(f(a))
''',
    'mutated_via_inner_alias': '''
def bump(xs):
    ys = xs
    ys[0] = 1.5


a = [1e300]
bump(a)


def f(items):
    return int(items[0])


print(f(a))
''',
    'mutated_via_alias': '''
a = [1e300]
b = a
b[0] = 1.5


def f(items):
    return int(items[0])


print(f(a))
''',
    'mutated_via_alias_chain': '''
a = [1e300]
b = a
c = b
c[0] = 1.5


def f(items):
    return int(items[0])


print(f(a))
''',
    'mutated_alias_source': '''
a = [1e300]
b = a
a[0] = 1.5


def f(items):
    return int(items[0])


print(f(b))
''',
    'shadowed_function': '''
def f(items):
    return int(items[0])


def other():
    def f(x):
        return 1.5
    return f([1e300])


print(other())
''',
    'shadowed_function_variable': '''
def f(items):
    return int(items[0])


def other():
    f = lambda x: 1.5
    return f([1e300])


print(other())
''',
    'alias_in_range': '''
a = [1.9]
b = a


def f(items):
    return int(items[0])


print(f(b))
''',
    'attribute_in_range': '''
class Box:
    items = [1.9]


def f(items):
    return int(items[0])


print(f(Box.items))
''',
    'dict_key_in_range': '''
def f(items):
    return int(items["v"])


print(f({"v": 1.9}))
''',
    'shadowed_int': '''
def f(items):
    def int(x):
        return x
    return int(items[0])


print(f([1e300]))
''',
    'closure_shadow': '''
a = [1e300]


def f(items):
    return int(items[0])


def outer():
    a = [1.5]

    def inner():
        return f(a)
    return inner()


print(outer())
''',
    'comprehension_shadow': '''
a = [1e300]


def f(items):
    return int(items[0])


print([f(a) for a in [[1.5]]])
''',
    'not_converted': '''
def f(items):
    return items[0]


print(f([1e300]))
''',
}


@unittest.skipUnless(HAVE_CC, 'gcc is required')
class IntFloatOutsideInt64ParameterItem(unittest.TestCase):
    def test_refused_by_name(self):
        for name, text in sorted(REFUSED.items()):
            check_refused(self, 'refuse_' + name, text)

    def test_matching_programs_are_cpython(self):
        for name, text in sorted(MATCH.items()):
            check_program(self, 'match_' + name, text)


if __name__ == '__main__':
    unittest.main()
