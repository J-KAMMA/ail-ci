"""pre333: int() of a statically known container is refused by name.

The rbpre311 review recorded a pre-existing bare container read as a difference: `a = [1e300]`
followed by `int(a)` ran on the general path (with a runtime TypeError whose text differs from
CPython) and the default build stopped with an incompatible `ail_flist` assignment, where CPython
raises TypeError.  This tree now refuses `int()` of a container value by name on both builds.

The check follows a module name bound once to a literal list, tuple, dict or set, aliases of it,
a subscript or dict lookup that yields a container, a known attribute, and a function argument
that its body converts with `int()`.  Scalars, strings, bytes, bytearray, a local shadow and a
container that is only read (not converted) keep their previous behaviour.
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
    return exe, subprocess.run([sys.executable, '-B', CHATGPT, 'compile', src.name,
                                '--syntax', 'python', '-o', exe.name], cwd=directory,
                               capture_output=True, text=True, timeout=900, env=env)


def check_refused(test, name, text):
    with tempfile.TemporaryDirectory(prefix='ail-pre333-') as directory:
        for general in (True, False):
            _, built = build(directory, name + ('g' if general else 'd'), text, general)
            test.assertNotEqual(built.returncode, 0, (name, general))
            message = built.stdout + built.stderr
            test.assertIn('int() of a ', message, (name, general, message[-1200:]))
            test.assertIn('container cannot be converted to an integer', message,
                          (name, general, message[-1200:]))


def check_program(test, name, text):
    with tempfile.TemporaryDirectory(prefix='ail-pre333-') as directory:
        want = cpython(directory, name, text)
        for general in (True, False):
            exe, built = build(directory, name, text, general)
            test.assertEqual(built.returncode, 0, built.stdout + built.stderr)
            got = subprocess.run([str(exe)], capture_output=True, timeout=120, cwd=directory)
            test.assertEqual(got.stdout.replace(b'\r\n', b'\n'), want[0], (name, general, got.stderr[-800:]))
            test.assertEqual(got.returncode, want[1], (name, general, got.stderr[-800:]))


REFUSED = {
    'module_list': '''
a = [1e300]
print(int(a))
''',
    'module_empty_list': '''
a = []
print(int(a))
''',
    'module_tuple': '''
a = (1e300,)
print(int(a))
''',
    'module_dict': '''
a = {"v": 1e300}
print(int(a))
''',
    'module_set': '''
a = {1e300}
print(int(a))
''',
    'alias_list': '''
a = [1e300]
b = a
print(int(b))
''',
    'alias_chain': '''
a = [1e300]
b = a
c = b
print(int(c))
''',
    'literal_list': '''
print(int([1e300]))
''',
    'literal_tuple': '''
print(int((1e300,)))
''',
    'literal_dict': '''
print(int({"v": 1e300}))
''',
    'literal_set': '''
print(int({1e300}))
''',
    'list_item': '''
xs = [[1e300]]
print(int(xs[0]))
''',
    'dict_value': '''
d = {"v": [1e300]}
print(int(d["v"]))
''',
    'attribute': '''
class Box:
    v = [1e300]


print(int(Box().v))
''',
    'argument': '''
def take(v):
    return int(v)


print(take([1e300]))
''',
    'keyword_argument': '''
def take(v):
    return int(v)


print(take(v=[1e300]))
''',
    'argument_chain': '''
def take(v):
    return int(v)


def outer(y):
    return take(y)


print(outer([1e300]))
''',
    'local_list': '''
def f():
    a = [1e300]
    return int(a)


print(f())
''',
    'local_list_item': '''
def f():
    xs = [[1e300]]
    return int(xs[0])


print(f())
''',
}

MATCH = {
    'string_and_bool': '''
print(int("42"), int(True), int(False))
''',
    'float_in_range': '''
print(int(1.9), int(-1.9), int(0.0))
''',
    'bytearray': '''
print(int(bytearray(b"10")))
''',
    'set_without_conversion': '''
a = {1e300}
print(len(a))
''',
    'dict_scalar_value': '''
d = {"v": 1.9}
print(int(d["v"]))
''',
    'local_shadow': '''
a = [1e300]


def f():
    a = 1.5
    return int(a)


print(f())
''',
    'nested_scalar': '''
a = [[1]]
print(int(a[0][0]))
''',
    'list_scalar_item': '''
a = [1.9]
print(int(a[0]))
''',
}


@unittest.skipUnless(HAVE_CC, 'gcc is required')
class ContainerIntRefusal(unittest.TestCase):
    def test_refused_by_name(self):
        for name, text in sorted(REFUSED.items()):
            check_refused(self, 'refuse_' + name, text)

    def test_matching_programs_are_cpython(self):
        for name, text in sorted(MATCH.items()):
            check_program(self, 'match_' + name, text)


if __name__ == '__main__':
    unittest.main()
