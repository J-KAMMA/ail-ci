"""Pre401: int() of a stored item in an instance/class container is refused by name.

The pre387 review recorded as pre-existing that ``c.v[0] = 1e300`` followed by
``c.k = int(c.v[0])`` compiled on both builds and then stopped with ``integer overflow``, where
CPython prints the exact big integer.  ``_known_class_attributes`` only saw plain
``self.attr = value`` stores, so a later subscript store, an attribute rebind or a list append
was invisible and the conversion ran at run time.  Constant stores now update the per-instance
(or class) value, so the conversion is refused by name on both builds.  A store whose key or
value is not static makes that attribute unknown, and a store of an in-range value still
matches CPython.
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


def check_refused(test, name, text, needle='int() of a float outside int64'):
    with tempfile.TemporaryDirectory(prefix='ail-pre401-') as directory:
        for general in (True, False):
            _, built = build(directory, name + ('g' if general else 'd'), text, general)
            test.assertNotEqual(built.returncode, 0, (name, general))
            message = built.stdout + built.stderr
            test.assertIn(needle, message, (name, general, message[-1200:]))
            test.assertNotIn('integer overflow', message, (name, general, message[-1200:]))


def check_program(test, name, text):
    with tempfile.TemporaryDirectory(prefix='ail-pre401-') as directory:
        want = cpython(directory, name, text)
        for general in (True, False):
            exe, built = build(directory, name, text, general)
            test.assertEqual(built.returncode, 0, built.stdout + built.stderr)
            got = subprocess.run([str(exe)], capture_output=True, timeout=120, cwd=directory)
            test.assertEqual(got.stdout.replace(b'\r\n', b'\n'), want[0], (name, general, got.stderr[-800:]))
            test.assertEqual(got.returncode, want[1], (name, general, got.stderr[-800:]))


REFUSED = {
    'subscript_store_then_field': '''
class C:
    def __init__(self):
        self.v = [0.0]
        self.k = 0

c = C()
c.v[0] = 1e300
c.k = int(c.v[0])
print(c.k)
''',
    'subscript_store_then_print': '''
class C:
    def __init__(self):
        self.v = [0.0]

c = C()
c.v[0] = 1e300
print(int(c.v[0]))
''',
    'attribute_rebind': '''
class C:
    def __init__(self):
        self.v = [0.0]
        self.k = 0

c = C()
c.v = [1e300]
c.k = int(c.v[0])
print(c.k)
''',
    'append': '''
class C:
    def __init__(self):
        self.v = []

c = C()
c.v.append(1e300)
print(int(c.v[0]))
''',
    'insert': '''
class C:
    def __init__(self):
        self.v = [0.0]

c = C()
c.v.insert(0, 1e300)
print(int(c.v[0]))
''',
    'negative': '''
class C:
    def __init__(self):
        self.v = [0.0]

c = C()
c.v[0] = -1e300
print(int(c.v[0]))
''',
    'negative_index': '''
class C:
    def __init__(self):
        self.v = [0.0, 1.0]

c = C()
c.v[-1] = 1e300
print(int(c.v[-1]))
''',
    'boundary': '''
class C:
    def __init__(self):
        self.v = [0.0]

c = C()
c.v[0] = 1e19
print(int(c.v[0]))
''',
    'alias': '''
class C:
    def __init__(self):
        self.v = [0.0]

c = C()
d = c
d.v[0] = 1e300
print(int(c.v[0]))
''',
    'list_instance': '''
class C:
    def __init__(self):
        self.v = [0.0]

c = C()
xs = [c]
c.v[0] = 1e300
print(int(xs[0].v[0]))
''',
    'dict_instance': '''
class C:
    def __init__(self):
        self.v = [0.0]

c = C()
items = {"c": c}
c.v[0] = 1e300
print(int(items["c"].v[0]))
''',
    'wrapper_argument': '''
class C:
    def __init__(self):
        self.v = [0.0]

c = C()
c.v[0] = 1e300


def take(x):
    return int(x)

print(take(c.v[0]))
''',
    'class_container': '''
class C:
    v = [0.0]

C.v[0] = 1e300
print(int(C.v[0]))
''',
    'dict_container': '''
class C:
    def __init__(self):
        self.d = {"k": 0.0}

c = C()
c.d["k"] = 1e300
print(int(c.d["k"]))
''',
    'module_constant_value': '''
X = 1e300


class C:
    def __init__(self):
        self.v = [0.0]

c = C()
c.v[0] = X
print(int(c.v[0]))
''',
    'store_back': '''
class C:
    def __init__(self):
        self.v = [0.0]

c = C()
c.v[0] = 1e300
c.v[0] = int(c.v[0])
print(c.v[0])
''',
    'string_big': ('''
class C:
    def __init__(self):
        self.v = [0.0]

c = C()
c.v[0] = "9223372036854775808"
print(int(c.v[0]))
''', 'int64 constant expression out of range'),
}

MATCH = {
    'in_range_float': '''
class C:
    def __init__(self):
        self.v = [0.0]

c = C()
c.v[0] = 1.5
print(int(c.v[0]))
''',
    'in_range_int': '''
class C:
    def __init__(self):
        self.v = [0.0]

c = C()
c.v[0] = 42
print(int(c.v[0]))
''',
    'upper_int64_float': '''
class C:
    def __init__(self):
        self.v = [0.0]

c = C()
c.v[0] = 9.0e18
print(int(c.v[0]))
''',
    'lower_int64_float': '''
class C:
    def __init__(self):
        self.v = [0.0]

c = C()
c.v[0] = -9.0e18
print(int(c.v[0]))
''',
    'store_field_in_range': '''
class C:
    def __init__(self):
        self.v = [0.0]
        self.k = 0

c = C()
c.v[0] = 1.5
c.k = int(c.v[0])
print(c.k)
''',
    'append_in_range': '''
class C:
    def __init__(self):
        self.v = [0.0]

c = C()
c.v.append(1.5)
print(int(c.v[0]))
''',
    'extend_keeps_index_zero': '''
class C:
    def __init__(self):
        self.v = [0.0]

c = C()
c.v.extend([1e300])
print(int(c.v[0]))
''',
    'last_store_wins': '''
class C:
    def __init__(self):
        self.v = [0.0]

c = C()
c.v[0] = 1e300
c.v[0] = 1.5
print(int(c.v[0]))
''',
    'two_instances_independent': '''
class C:
    def __init__(self):
        self.v = [0.0]

a = C()
b = C()
b.v[0] = 1e300
print(int(a.v[0]))
''',
    'dynamic_after_out_of_range': '''
class C:
    def __init__(self):
        self.v = [0.0]

c = C()
c.v[0] = 1e300
x = 1.5
c.v[0] = x
print(int(c.v[0]))
''',
    'dict_in_range': '''
class C:
    def __init__(self):
        self.d = {"k": 0.0}

c = C()
c.d["k"] = 1.5
print(int(c.d["k"]))
''',
    'class_container_in_range': '''
class C:
    v = [0.0]

C.v[0] = 1.5
print(int(C.v[0]))
''',
    'string_in_range': '''
class C:
    def __init__(self):
        self.v = [0.0]

c = C()
c.v[0] = "42"
print(int(c.v[0]))
''',
}


@unittest.skipUnless(HAVE_CC, 'gcc is required')
class IntFloatStoredContainerOutsideInt64(unittest.TestCase):
    def test_refused_by_name(self):
        for name, value in sorted(REFUSED.items()):
            if isinstance(value, tuple):
                text, needle = value
            else:
                text, needle = value, 'int() of a float outside int64'
            check_refused(self, 'refuse_' + name, text, needle)

    def test_conversions_that_fit_are_cpython(self):
        for name, text in sorted(MATCH.items()):
            check_program(self, 'match_' + name, text)


if __name__ == '__main__':
    unittest.main()
