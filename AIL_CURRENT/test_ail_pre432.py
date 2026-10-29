"""pre432: deleting an item of a class object uses CPython's deletion wording.

The pre395 reviewer recorded as pre-existing that ``del A[0]`` on ``class A`` said
``TypeError: 'type' object doesn't support item deletion`` on both builds, where CPython
says ``TypeError: 'type' object does not support item deletion``.  Only a class object
differs: an instance, an exception instance and a str keep CPython's ``doesn't`` text.
"""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent
CHATGPT = str(ROOT / 'ail_chatgpt.py')


def cpython(directory, name, text):
    src = Path(directory) / (name + '_cpython.py')
    src.write_text(text, encoding='utf-8')
    return subprocess.run([sys.executable, '-B', str(src)], capture_output=True, timeout=120,
                          env=dict(os.environ, PYTHONUTF8='1', PYTHONWARNINGS='ignore'))


def build(directory, name, text, general):
    src = Path(directory) / (name + '.py')
    src.write_text(text, encoding='utf-8')
    exe = Path(directory) / ('exe_' + name + ('_g' if general else '_d'))
    env = dict(os.environ, AIL_NO_CACHE='1', AIL_QUIET_FALLBACK='1')
    env.pop('AIL_NO_GENERAL', None)
    if general:
        env['AIL_UNIFIED_FORCE'] = '1'
    else:
        env.pop('AIL_UNIFIED_FORCE', None)
    return exe, subprocess.run([sys.executable, '-B', CHATGPT, 'compile', src.name,
                                '--syntax', 'python', '-o', exe.name], cwd=directory,
                               capture_output=True, text=True, timeout=900, env=env)


class Pre432Tests(unittest.TestCase):
    def check(self, name, text):
        with tempfile.TemporaryDirectory(prefix='ail-pre432-') as directory:
            want = cpython(directory, name, text)
            for general in (True, False):
                exe, built = build(directory, name, text, general)
                self.assertEqual(built.returncode, 0, (name, general, built.stdout + built.stderr))
                got = subprocess.run([str(exe)], capture_output=True, timeout=120, cwd=directory)
                self.assertEqual(got.stdout, want.stdout, (name, general, got.stderr[-800:]))
                self.assertEqual(got.returncode, want.returncode, (name, general, got.stderr[-800:]))

    def test_class_object_delitem(self):
        self.check('keys', '''
class A:
    pass


class B(A):
    pass


def drop(x, k):
    try:
        del x[k]
    except Exception as e:
        print(type(e).__name__, e)


for label, key in [('zero', 0), ('neg', -1), ('bool', True), ('wide', 2 ** 40),
                   ('str', 'x'), ('none', None), ('tuple', (1, 2))]:
    drop(A, key)
drop(B, 0)
drop(A, slice(1, 2))
drop(B, slice(None, None, -1))
try:
    del A[0]
except Exception as e:
    print('stmt', type(e).__name__, e)
''')

    def test_routes_to_a_class_value(self):
        self.check('routes', '''
class A:
    pass


class B(A):
    pass


class Holder:
    pass


def drop(x):
    try:
        del x[0]
    except Exception as e:
        print(type(e).__name__, e)


def pick():
    return B


holder = Holder()
holder.k = B
items = [A, B]
mapping = {'a': A, 'b': B}
alias = B
for label, obj in [('direct', A), ('alias', alias), ('arg', B), ('item', items[1]),
                   ('dict', mapping['b']), ('attr', holder.k), ('return', pick())]:
    print(label, end=' ')
    drop(obj)
''')

    def test_non_class_deletion_unchanged(self):
        self.check('nonclass', '''
class A:
    pass


class E(Exception):
    pass


def drop(label, value):
    try:
        del value[0]
    except Exception as e:
        print(label, type(e).__name__, e)


drop('instance', A())
drop('exception', E())
drop('str', 'x')
drop('tuple', (1, 2))
''')


if __name__ == '__main__':
    unittest.main()
