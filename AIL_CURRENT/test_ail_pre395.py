"""pre395: a class object subscript names the class, as CPython does.

The pre377 reviewer recorded as pre-existing that ``class A: pass; A[0]`` stopped with
``TypeError: 'type' object is not subscriptable`` on both builds, where CPython says
``TypeError: type 'A' is not subscriptable``.  The general-path runtime now names the class
object's own class in that error, for an index and for a slice; a class alias, an inherited
class and a value reaching the subscript through an argument, a list item, an attribute or a
dict value all name the class that is actually subscribed.  Item assignment/deletion keep
CPython's ``'type' object ...`` wording, and instances are untouched.
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
    return exe, subprocess.run([sys.executable, '-B', CHATGPT, 'compile', src.name, '--syntax', 'python',
                                '-o', exe.name], cwd=directory, capture_output=True, text=True, timeout=900, env=env)


class Pre395Tests(unittest.TestCase):
    def check(self, name, text):
        with tempfile.TemporaryDirectory(prefix='ail-pre395-') as directory:
            want = cpython(directory, name, text)
            for general in (True, False):
                exe, built = build(directory, name, text, general)
                self.assertEqual(built.returncode, 0, (name, general, built.stdout + built.stderr))
                got = subprocess.run([str(exe)], capture_output=True, timeout=120, cwd=directory)
                self.assertEqual(got.stdout, want.stdout, (name, general, got.stderr[-800:]))
                self.assertEqual(got.returncode, want.returncode, (name, general, got.stderr[-800:]))

    def test_class_object_index(self):
        self.check('index', '''
class A:
    pass


class B(A):
    pass


def show(label, c, key):
    try:
        c[key]
    except TypeError as e:
        print(label, type(e).__name__, e)


def main():
    show('A0', A, 0)
    show('Aneg', A, -1)
    show('Awide', A, 2 ** 40)
    show('Anone', A, None)
    show('Afloat', A, 0.0)
    show('Astr', A, 'x')
    show('Aempty', A, '')
    show('Atuple', A, (0, 1))
    show('Abool', A, True)
    show('B0', B, 0)
    alias = A
    show('alias', alias, 0)


main()
''')

    def test_class_object_slice(self):
        self.check('slice', '''
class A:
    pass


class B(A):
    pass


def show(label, c, key):
    try:
        c[key]
    except TypeError as e:
        print(label, type(e).__name__, e)


def main():
    show('full', A, slice(1, 2))
    show('open', A, slice(None, None))
    show('step', A, slice(None, None, 2))
    show('negative', A, slice(-2, -1))
    show('empty', A, slice(2, 2))
    show('reverse', A, slice(None, None, -1))
    show('subclass', B, slice(0, 1))


main()
''')

    def test_class_object_through_routes_and_dunder_patch(self):
        self.check('routes', '''
class A:
    def __add__(self, other):
        return 1


class Box:
    pass


def get(c, key):
    try:
        c[key]
    except TypeError as e:
        return type(e).__name__ + ' ' + str(e)


def make():
    return A


def main():
    b = Box()
    b.c = A
    d = {'k': A}
    print(get(A, 0))
    print(get([A][0], 0))
    print(get(d['k'], 0))
    print(get(b.c, -1))
    print(get(make(), 2 ** 40))
    print(get(A, slice(1, 3)))
    print(get([A][0], slice(None, None, -1)))
    try:
        A[0] = 1
    except TypeError as e:
        print('set', type(e).__name__, e)


main()
''')


if __name__ == '__main__':
    unittest.main()
