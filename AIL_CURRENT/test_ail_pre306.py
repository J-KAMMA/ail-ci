"""Pre306: int() of a float outside int64 reached through an attribute is refused by name.

CPython has unbounded integers, so ``int(C().v)`` with a class attribute ``v = 1e300`` prints a
301-digit integer.  AIL integers are signed int64, so such a conversion has no answer here.  The
front end now folds a literal class attribute, a literal ``self.attr`` set in ``__init__``, and
those values reached through a class alias, a module constant, a module instance, a list/tuple or
dict item, an argument or a keyword argument, and refuses them with ``int() of a float outside
int64 ... big integer`` on both builds.  In-range attributes, shadowed class names and values
mutated after construction are unchanged and still compared with CPython.
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
    with tempfile.TemporaryDirectory(prefix='ail-pre306-') as directory:
        for general in (True, False):
            _, built = build(directory, name + ('g' if general else 'd'), text, general)
            test.assertNotEqual(built.returncode, 0, (name, general))
            message = built.stdout + built.stderr
            test.assertIn('int() of a float outside int64', message, (name, general, message[-1200:]))
            test.assertIn('big integer', message, (name, general, message[-1200:]))


def check_program(test, name, text):
    with tempfile.TemporaryDirectory(prefix='ail-pre306-') as directory:
        want = cpython(directory, name, text)
        for general in (True, False):
            exe, built = build(directory, name, text, general)
            test.assertEqual(built.returncode, 0, built.stdout + built.stderr)
            got = subprocess.run([str(exe)], capture_output=True, timeout=120, cwd=directory)
            test.assertEqual(got.stdout.replace(b'\r\n', b'\n'), want[0], (name, general, got.stderr[-800:]))
            test.assertEqual(got.returncode, want[1], (name, general, got.stderr[-800:]))


REFUSED = {
    'class_attribute': '''
class C:
    v = 1e300

print(int(C().v))
''',
    'class_attribute_direct': '''
class C:
    v = 1e300

print(int(C.v))
''',
    'class_attribute_negative': '''
class C:
    v = -1e300

print(int(C().v))
''',
    'init_attribute': '''
class C:
    def __init__(self):
        self.v = 1e300

print(int(C().v))
''',
    'module_constant_attribute': '''
x = 1e300


class C:
    v = x

print(int(C().v))
''',
    'alias_attribute': '''
class C:
    v = 1e300

D = C
print(int(D().v))
''',
    'list_instance': '''
class C:
    v = 1e300

items = [C()]
print(int(items[0].v))
''',
    'dict_instance': '''
class C:
    v = 1e300

items = {"c": C()}
print(int(items["c"].v))
''',
    'through_argument': '''
class C:
    v = 1e300


def identity(x):
    return x

print(int(identity(C().v)))
''',
    'through_wrapper': '''
class C:
    v = 1e300


def take(x):
    return int(x)

print(take(C().v))
''',
    'instance_name': '''
class C:
    v = 1e300

c = C()
print(int(c.v))
''',
}

MATCH = {
    'in_range_class_and_instance': '''
class C:
    v = 1.5


class D:
    def __init__(self):
        self.v = -1.5


def take(x):
    return int(x)

c = C()
d = D()
print(int(C().v), int(C.v), int(c.v))
print(int(d.v), int(9.0e18), int(-9.0e18))
print(take(c.v))
''',
    'mutated_after_construction': '''
class C:
    v = 1.5

c = C()
c.v = 9.0e18
print(int(c.v))
''',
    'in_range_containers': '''
class C:
    v = 1.5

items = [C()]
values = {"c": C()}
i = 0
print(int(items[0].v), int(values["c"].v), int(items[i].v))
''',
    'shadowed_class_name': '''
class C:
    v = 1e300


class D:
    v = 1.5


def f(C):
    return int(C().v)

print(f(D))
''',
    'attribute_in_expression_that_fits': '''
class C:
    v = 1e300

x = C()
print(int(x.v * 0), int(x.v - x.v))
''',
}


@unittest.skipUnless(HAVE_CC, 'gcc is required')
class IntFloatAttributeOutsideInt64(unittest.TestCase):
    def test_refused_by_name(self):
        for name, text in sorted(REFUSED.items()):
            check_refused(self, 'refuse_' + name, text)

    def test_conversions_that_fit_are_cpython(self):
        for name, text in sorted(MATCH.items()):
            check_program(self, 'match_' + name, text)


if __name__ == '__main__':
    unittest.main()
