"""Pre407: an attribute-held container item read before a later store is refused by name.

The pre388 review recorded as pre-existing that
``class C: pass; c = C(); c.a = [1e300]; print(int(c.a[0])); c.a[0] = 1.5``
compiled on both builds and then stopped with ``integer overflow``, where CPython prints the big
integer.  Attribute-held containers were not folded, so the read did not see the literal item.
Module-level attribute stores are now replayed in source order; an item read before a later
assignment, rebind, append, insert or deletion is folded and the conversion is refused by name.
Class-held containers and instances reached through aliases, other containers or arguments use
the same path.  Reads inside deferred function, lambda and method bodies are still checked
without the module's later stores, and in-range or already-mutated values are unchanged and
still compared with CPython.
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

FLOAT = 'int() of a float outside int64'
INT = 'int64 constant expression out of range'


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


def check_refused(test, name, text, needle):
    with tempfile.TemporaryDirectory(prefix='ail-pre407-') as directory:
        for general in (True, False):
            _, built = build(directory, name + ('g' if general else 'd'), text, general)
            test.assertNotEqual(built.returncode, 0, (name, general))
            message = built.stdout + built.stderr
            test.assertIn(needle, message, (name, general, message[-1200:]))
            test.assertNotIn('integer overflow', message, (name, general, message[-1200:]))


def check_program(test, name, text):
    with tempfile.TemporaryDirectory(prefix='ail-pre407-') as directory:
        want = cpython(directory, name, text)
        for general in (True, False):
            exe, built = build(directory, name, text, general)
            test.assertEqual(built.returncode, 0, built.stdout + built.stderr)
            got = subprocess.run([str(exe)], capture_output=True, timeout=120, cwd=directory)
            test.assertEqual(got.stdout.replace(b'\r\n', b'\n'), want[0], (name, general, got.stderr[-800:]))
            test.assertEqual(got.returncode, want[1], (name, general, got.stderr[-800:]))


REFUSED = {
    'recorded_attribute_list': ('''
class C:
    pass

c = C()
c.a = [1e300]
print(int(c.a[0]))
c.a[0] = 1.5
''', FLOAT),
    'init_attribute_subscript': ('''
class C:
    def __init__(self):
        self.v = [0.0]

c = C()
c.v[0] = 1e300
print(int(c.v[0]))
''', FLOAT),
    'attribute_rebind': ('''
class C:
    def __init__(self):
        self.v = [0.0]

c = C()
c.v = [1e300]
print(int(c.v[0]))
''', FLOAT),
    'read_before_attribute_rebind': ('''
class C:
    def __init__(self):
        self.v = [1e300]

c = C()
print(int(c.v[0]))
c.v = [1.5]
''', FLOAT),
    'attribute_append': ('''
class C:
    def __init__(self):
        self.v = []

c = C()
c.v.append(1e300)
print(int(c.v[0]))
''', FLOAT),
    'class_container_subscript': ('''
class C:
    v = [0.0]

C.v[0] = 1e300
print(int(C.v[0]))
''', FLOAT),
    'class_container_rebind': ('''
class C:
    v = [0.0]

C.v = [1e300]
print(int(C.v[0]))
''', FLOAT),
    'dict_value': ('''
class C:
    def __init__(self):
        self.d = {"k": 0.0}

c = C()
c.d["k"] = 1e300
print(int(c.d["k"]))
''', FLOAT),
    'negative': ('''
class C:
    def __init__(self):
        self.v = [0.0]

c = C()
c.v[0] = -1e300
print(int(c.v[0]))
''', FLOAT),
    'boundary_outside_int64': ('''
class C:
    def __init__(self):
        self.v = [0.0]

c = C()
c.v[0] = 1e19
print(int(c.v[0]))
''', FLOAT),
    'string_outside_int64': ('''
class C:
    def __init__(self):
        self.v = [0]

c = C()
c.v[0] = "9223372036854775808"
print(int(c.v[0]))
''', INT),
    'alias_instance': ('''
class C:
    def __init__(self):
        self.v = [0.0]

c = C()
d = c
d.v[0] = 1e300
print(int(c.v[0]))
''', FLOAT),
    'list_item_instance': ('''
class C:
    def __init__(self):
        self.v = [0.0]

c = C()
items = [c]
c.v[0] = 1e300
print(int(items[0].v[0]))
''', FLOAT),
    'dict_value_instance': ('''
class C:
    def __init__(self):
        self.v = [0.0]

c = C()
items = {"c": c}
c.v[0] = 1e300
print(int(items["c"].v[0]))
''', FLOAT),
    'through_argument': ('''
class C:
    def __init__(self):
        self.v = [0.0]

c = C()
c.v[0] = 1e300


def identity(x):
    return x

print(int(identity(c.v[0])))
''', FLOAT),
    'through_wrapper': ('''
class C:
    def __init__(self):
        self.v = [0.0]

c = C()
c.v[0] = 1e300


def take(x):
    return int(x)

print(take(c.v[0]))
''', FLOAT),
}

MATCH = {
    'mutated_first': '''
class C:
    pass

c = C()
c.a = [1e300]
c.a[0] = 1.5
print(int(c.a[0]))
''',
    'in_range_subscript': '''
class C:
    def __init__(self):
        self.v = [0.0]

c = C()
c.v[0] = 1.5
print(int(c.v[0]))
''',
    'in_range_rebind': '''
class C:
    def __init__(self):
        self.v = [0.0]

c = C()
c.v = [1.5]
print(int(c.v[0]))
''',
    'two_instances': '''
class C:
    def __init__(self):
        self.v = [0.0]

a = C()
b = C()
b.v[0] = 1e300
print(int(a.v[0]))
''',
    'in_range_class_container': '''
class C:
    v = [0.0]

C.v[0] = 1.5
print(int(C.v[0]))
''',
    'function_body_after_instance_store': '''
class C:
    def __init__(self, v):
        self.v = v

c = C(1e300)


def f():
    print(int(c.v))


c.v = 1.5
f()
''',
    'lambda_after_instance_store': '''
class C:
    def __init__(self, v):
        self.v = v

c = C(1e300)
f = lambda: int(c.v)
c.v = 1.5
print(f())
''',
    'method_after_instance_store': '''
class C:
    def __init__(self, v):
        self.v = v

c = C(1e300)


class D:
    def show(self):
        print(int(c.v))


c.v = 1.5
D().show()
''',
    'unknown_call_before_read': '''
class C:
    pass

c = C()
c.a = [1e300]


def touch():
    c.a[0] = 1.5


touch()
print(int(c.a[0]))
''',
    'in_range_through_argument': '''
class C:
    def __init__(self):
        self.v = [1.5]

c = C()
print(int(c.v[0]))
''',
}


@unittest.skipUnless(HAVE_CC, 'gcc is required')
class AttributeContainerItemOutsideInt64(unittest.TestCase):
    def test_refused_by_name(self):
        for name, (text, needle) in sorted(REFUSED.items()):
            check_refused(self, 'refuse_' + name, text, needle)

    def test_values_that_fit_are_cpython(self):
        for name, text in sorted(MATCH.items()):
            check_program(self, 'match_' + name, text)


if __name__ == '__main__':
    unittest.main()
