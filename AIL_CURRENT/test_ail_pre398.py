"""pre398: a class body's indirect self-read through a function is refused by name.

The pre382 review recorded as pre-existing that a module function reading the class being
defined, called as a class-attribute value, returned the class object where CPython raises
``NameError`` because the class name is not bound until the body has finished.  The direct
reads are pre382's feature; this indirect function route is now refused by name at compile
time on both builds.  A function that reads another class, a parameter/local named like the
class, and calls made after the class body still match CPython.
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
    else:
        env.pop('AIL_UNIFIED_FORCE', None)
    return exe, subprocess.run([sys.executable, '-B', CHATGPT, 'compile', src.name, '--syntax', 'python',
                                '-o', exe.name], cwd=directory, capture_output=True, text=True, timeout=900, env=env)


def check_refused(test, name, text, message='while the class body is running'):
    with tempfile.TemporaryDirectory(prefix='ail-pre398-') as directory:
        for general in (True, False):
            _, built = build(directory, name + ('g' if general else 'd'), text, general)
            test.assertNotEqual(built.returncode, 0, (name, general))
            output = built.stdout + built.stderr
            test.assertIn(message, output, (name, general, output[-1200:]))


def check_program(test, name, text):
    with tempfile.TemporaryDirectory(prefix='ail-pre398-') as directory:
        want = cpython(directory, name, text)
        for general in (True, False):
            exe, built = build(directory, name, text, general)
            test.assertEqual(built.returncode, 0, (name, general, built.stdout + built.stderr))
            got = subprocess.run([str(exe)], capture_output=True, timeout=120, cwd=directory)
            test.assertEqual(got.stdout.replace(b'\r\n', b'\n'), want[0], (name, general, got.stderr[-800:]))
            test.assertEqual(got.returncode, want[1], (name, general, got.stderr[-800:]))


REFUSED = {
    'direct': '''
def get():
    return C
class C:
    x = get()
print(C.x)
''',
    'list_item': '''
def get():
    return C
class C:
    x = [get()][0]
print(C.x)
''',
    'dict_value': '''
def get():
    return C
class C:
    x = {"k": get()}["k"]
print(C.x)
''',
    'tuple_item': '''
def get():
    return C
class C:
    x = (get(), 1)[0]
print(C.x)
''',
    'nested_argument': '''
def take(v):
    return v
def get():
    return C
class C:
    x = take(get())
print(C.x)
''',
    'wrapper': '''
def get():
    return C
def wrap():
    return get()
class C:
    x = wrap()
print(C.x)
''',
}


MATCH = {
    'plain_function': '''
def get():
    return 1
class C:
    x = get()
print(C.x)
''',
    'other_class': '''
class A:
    pass
def get():
    return A
class C:
    x = get()
print(C.x is A)
''',
    'parameter_shadow': '''
def get(C):
    return C
class C:
    x = get(5)
print(C.x)
''',
    'local_shadow': '''
def get():
    C = 3
    return C
class C:
    x = get()
print(C.x)
''',
    'after_definition': '''
def get():
    return C
class C:
    pass
print(get() is C)
''',
    'alias_after_definition': '''
def get():
    return C
class C:
    pass
f = get
print(f() is C)
''',
    'function_argument': '''
def take(v):
    return v
class C:
    x = take(7)
print(C.x)
''',
}


@unittest.skipUnless(HAVE_CC, 'gcc is required')
class ClassBodyIndirectSelfRead(unittest.TestCase):
    def test_refused_by_name(self):
        for name, text in sorted(REFUSED.items()):
            check_refused(self, 'refuse_' + name, text)

    def test_matching_controls(self):
        for name, text in sorted(MATCH.items()):
            check_program(self, 'match_' + name, text)


if __name__ == '__main__':
    unittest.main()
