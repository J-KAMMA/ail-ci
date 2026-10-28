"""pre402: a function-local int() read before a later container mutation is refused.

The pre387 review recorded as pre-existing that a function-local container read before a later
mutation stopped with ``integer overflow`` on both builds, where CPython prints the exact big
integer::

    def f():
        items = [1e300]
        print(int(items[0]))
        items[0] = 1.5

    f()

The scope flow pass now follows a function's own top-level literal containers, aliases and
scalars in source order, so the read is refused by name before the later mutation.  A mutation
before the read, an in-range value and a value at the int64 boundary still match CPython.
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
RANGE = 'int64 constant expression out of range'

REFUSED = {
    'local_list': ('''
def f():
    items = [1e300]
    print(int(items[0]))
    items[0] = 1.5


f()
''', FLOAT),
    'local_dict_get': ('''
def f():
    d = {"k": 1e300}
    print(int(d.get("k")))
    d["k"] = 1.5


f()
''', FLOAT),
    'local_dict_subscript': ('''
def f():
    d = {"k": 1e300}
    print(int(d["k"]))
    d.update({"k": 1.5})


f()
''', FLOAT),
    'local_alias': ('''
def f():
    items = [1e300]
    a = items
    print(int(a[0]))
    items[0] = 1.5


f()
''', FLOAT),
    'local_alias_chain': ('''
def f():
    items = [1e300]
    a = items
    b = a
    print(int(b[0]))
    a[0] = 1.5


f()
''', FLOAT),
    'local_nested': ('''
def f():
    d = {"k": [1e300]}
    print(int(d["k"][0]))
    d["k"][0] = 1.5


f()
''', FLOAT),
    'local_negative_index': ('''
def f():
    items = [1e300]
    print(int(items[-1]))
    items[0] = 1.5


f()
''', FLOAT),
    'local_empty_dict_default': ('''
def f():
    d = {}
    print(int(d.get("k", 1e300)))
    d.update({"k": 1.5})


f()
''', FLOAT),
    'local_tuple': ('''
def f():
    items = (1e300, 1.5)
    print(int(items[0]))
    items = (1.5, 2.5)


f()
''', FLOAT),
    'local_del_after_read': ('''
def f():
    items = [1e300]
    print(int(items[0]))
    del items[0]


f()
''', FLOAT),
    'local_big_string': ('''
def f():
    d = {"k": "9223372036854775808"}
    print(int(d.get("k")))
    d.update({"k": "1"})


f()
''', RANGE),
}

MATCH = {
    'local_list_mutation_first': '''
def f():
    items = [1e300]
    items[0] = 1.5
    print(int(items[0]))


f()
''',
    'local_dict_update_first': '''
def f():
    d = {"k": 1e300}
    d.update({"k": 1.5})
    print(int(d.get("k")))


f()
''',
    'local_alias_mutation_first': '''
def f():
    items = [1e300]
    a = items
    a[0] = 1.5
    print(int(items[0]))


f()
''',
    'local_method_mutation_first': '''
def f():
    items = [1e300]
    items.clear()
    items.append(1.5)
    print(int(items[0]))


f()
''',
    'local_inrange': '''
def f():
    items = [5]
    print(int(items[0]))
    items[0] = 1.5


f()
''',
    'local_int64_max': '''
def f():
    items = [9223372036854775807]
    print(int(items[0]))
    items[0] = 0


f()
''',
    'local_tuple_rebound_first': '''
def f():
    items = (1e300, 1.5)
    items = (1.5, 2.5)
    print(int(items[0]))


f()
''',
}


def cpython(directory, name, text):
    src = Path(directory) / (name + '_cpython.py')
    src.write_text(text, encoding='utf-8')
    return subprocess.run([sys.executable, '-B', str(src)], capture_output=True, timeout=120,
                          env=dict(os.environ, PYTHONUTF8='1', PYTHONWARNINGS='ignore'))


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
                                '-o', exe.name], cwd=directory, capture_output=True, text=True,
                               timeout=900, env=env)


def check_refused(test, name, text, needle):
    with tempfile.TemporaryDirectory(prefix='ail-pre402-') as directory:
        for general in (True, False):
            _, built = build(directory, name + ('g' if general else 'd'), text, general)
            output = built.stdout + built.stderr
            test.assertNotEqual(built.returncode, 0, (name, general, output[-1200:]))
            test.assertIn(needle, output, (name, general, output[-1200:]))
            test.assertNotIn('integer overflow', output, (name, general, output[-1200:]))


def check_program(test, name, text):
    with tempfile.TemporaryDirectory(prefix='ail-pre402-') as directory:
        want = cpython(directory, name, text)
        for general in (True, False):
            exe, built = build(directory, name, text, general)
            test.assertEqual(built.returncode, 0, (name, general, built.stdout + built.stderr))
            got = subprocess.run([str(exe)], capture_output=True, timeout=120, cwd=directory)
            test.assertEqual(got.stdout.replace(b'\r\n', b'\n'), want.stdout,
                             (name, general, got.stderr[-800:]))
            test.assertEqual(got.returncode, want.returncode, (name, general, got.stderr[-800:]))


@unittest.skipUnless(HAVE_CC, 'gcc is required')
class LocalFlowInt64Tests(unittest.TestCase):
    def test_read_before_mutation_is_refused(self):
        for name, (text, needle) in sorted(REFUSED.items()):
            check_refused(self, 'refuse_' + name, text, needle)

    def test_mutation_before_read_matches_cpython(self):
        for name, text in sorted(MATCH.items()):
            check_program(self, 'match_' + name, text)


if __name__ == '__main__':
    unittest.main()
