"""pre409: a class value's subscript TypeError names the class, as CPython does.

The pre378 review recorded as pre-existing that ``A[1]`` for a user class said
``'type' object is not subscriptable`` on both builds, where CPython 3.12 says
``type 'A' is not subscriptable``.  The general-path runtime now formats that message
from the class value's own name for index and slice reads, with CPython's 200-character
message limit; assignment keeps CPython's bare ``'type' object ...`` wording (deletion still
has the pre-existing ``doesn't`` wording), and instance ``__getitem__`` is unchanged.
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


class Pre409Tests(unittest.TestCase):
    def check(self, name, text):
        with tempfile.TemporaryDirectory(prefix='ail-pre409-') as directory:
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


class _AilDeque_Foo:
    pass


class Holder:
    pass


def identity(c):
    return c


def sub(label, c, k):
    try:
        c[k]
    except TypeError as e:
        print(label, type(e).__name__, e)


def main():
    sub('int', A, 1)
    sub('zero', A, 0)
    sub('negative', A, -1)
    sub('str', A, 'x')
    sub('none', A, None)
    sub('tuple', A, (1, 2))
    sub('subclass', B, 1)
    sub('weird_name', _AilDeque_Foo, 1)
    alias = A
    sub('alias', alias, 1)
    sub('argument', identity(A), 1)
    sub('list_item', [A][0], 1)
    h = Holder()
    h.c = A
    sub('attribute', h.c, 1)
    sub('dict_value', {'k': A}['k'], 1)
    sub('dict_get', {'k': A}.get('k'), 1)


main()
''')

    def test_class_object_slice(self):
        self.check('slice', '''
class A:
    pass


class B(A):
    pass


class Holder:
    pass


def identity(c):
    return c


def sub(label, c, lo, hi):
    try:
        c[lo:hi]
    except TypeError as e:
        print(label, type(e).__name__, e)


def sub_all(label, c):
    try:
        c[:]
    except TypeError as e:
        print(label + '_all', type(e).__name__, e)
    try:
        c[::-1]
    except TypeError as e:
        print(label + '_step', type(e).__name__, e)


def main():
    sub('slice', A, 1, 2)
    sub('empty_slice', A, 2, 2)
    sub('negative_slice', A, -2, -1)
    sub('none_slice', A, None, None)
    sub('subclass', B, 0, 3)
    sub_all('A', A)
    alias = A
    sub('alias', alias, 0, 1)
    sub('argument', identity(A), 0, 1)
    sub('list_item', [A][0], 0, 1)
    h = Holder()
    h.c = A
    sub('attribute', h.c, 0, 1)
    sub('dict_value', {'k': A}['k'], 0, 1)


main()
''')

    def test_class_object_long_names(self):
        names = ['A' * 95, 'A' * 96, 'A' * 100, 'A' * 199, 'A' * 200, 'A' * 201, 'B' * 300]
        lines = ['def sub(label, c, k):', '    try:', '        c[k]', '    except TypeError as e:',
                 '        print(label, type(e).__name__, e)', '', 'def sub_slice(label, c):',
                 '    try:', '        c[0:1]', '    except TypeError as e:',
                 '        print(label, type(e).__name__, e)', '']
        for i, name in enumerate(names):
            lines += ['class ' + name + ':', '    pass', '']
        lines += ['def main():']
        for i, name in enumerate(names):
            lines += ['    sub(\'index%d\', %s, 1)' % (i, name)]
            lines += ['    sub_slice(\'slice%d\', %s)' % (i, name)]
        lines += ['', 'main()', '']
        self.check('long_names', '\n'.join(lines))

    def test_class_object_assignment_and_instance_control(self):
        self.check('controls', '''
class A:
    pass


class Box:
    def __init__(self):
        self.v = 42

    def __getitem__(self, k):
        return self.v


def assign(c):
    try:
        c[1] = 2
    except TypeError as e:
        print(type(e).__name__, e)


def main():
    assign(A)
    print(Box()[1])
    print(Box()[0:2])
    try:
        A[1]
    except TypeError as e:
        print(type(e).__name__, e)


main()
''')


if __name__ == '__main__':
    unittest.main()
