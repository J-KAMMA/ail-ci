# -*- coding: utf-8 -*-
"""pre272: deleting a list item that is out of range names CPython's message.

CPython raises ``IndexError: list assignment index out of range`` for ``del xs[i]``, also when
the list is empty or the index is negative (including INT64_MIN).  AIL used the read-side text
(``list index out of range``), or the ``pop()`` texts (``pop from empty list`` / ``pop index out
of range``), so an uncaught delete printed a different message on both builds.  The general
path's list delete and the typed path's int/float/numeric-field/string-field delete now use the
assignment text; ``list.pop()`` keeps its own two messages, and in-range deletes are unchanged.
"""
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent
CLI = ROOT / 'ail_chatgpt.py'
HAVE_CC = shutil.which('gcc') is not None

UNCAUGHT = (
    'a = []\nprint(a)\ndel a[0]\n',
    'a = [1, 2, 3]\nprint(a)\ndel a[9]\n',
    'a = [1, 2, 3]\nprint(a)\ndel a[-2**63]\n',
    "a = ['a', 'b']\nprint(a)\ndel a[7]\n",
    'a = [1.0, 2.0]\nprint(a)\ndel a[7]\n',
    'class C:\n    def __init__(self):\n        self.xs = [1, 2]\n'
    'c = C()\nprint(c.xs)\ndel c.xs[7]\n',
    'class C:\n    def __init__(self):\n        self.xs = ["a", "b"]\n'
    'c = C()\nprint(c.xs)\ndel c.xs[7]\n',
)

CAUGHT = '''def attempt(xs, i):
    try:
        del xs[i]
    except IndexError as e:
        print(type(e).__name__, str(e), e.args)

a = [1, 2, 3]
attempt(a, 9)
attempt(a, -9)
attempt([], 0)
attempt(['a', 'b'], 5)
attempt([1.0, 2.0], 5)
attempt([1, 'x', [2]], 5)
attempt(b'a b'.split(), 5)
attempt([[1], [2]][0], 5)
d = {'xs': [1, 2]}
attempt(d['xs'], 5)
print(d)

class Box:
    def __init__(self):
        self.xs = [1, 2]
        self.ys = ['a', 'b']
        self.zs = [1.0, 2.0]

box = Box()
for name in ('xs', 'ys', 'zs'):
    try:
        del getattr(box, name)[5]
    except IndexError as e:
        print(type(e).__name__, str(e), e.args)
print(box.xs, box.ys, box.zs)
'''

CAUGHT_NO_TEXT = '''def attempt(xs, i):
    try:
        del xs[i]
    except IndexError:
        print("caught", xs)

attempt([], 0)
attempt([1, 2, 3], 9)
attempt([1, 2, 3], -9)

class C:
    def __init__(self):
        self.i = [1, 2, 3]
        self.f = [1.5, 2.5]
        self.s = ['a', 'b']

c = C()
attempt(c.i, 9)
attempt(c.f, 9)
attempt(c.s, 9)
print(c.i, c.f, c.s)
'''

IN_RANGE = '''a = list(range(6))
del a[1]
del a[-1]
del a[0:0]
print(a)
del a[::2]
print(a)

class C:
    def __init__(self):
        self.i = [1, 2, 3]
        self.s = ['a', 'b', 'c']
        self.f = [1.0, 2.0, 3.0]

c = C()
del c.i[1]
del c.s[0]
del c.f[-1]
print(c.i, c.s, c.f)

b = []
try:
    b.pop()
except IndexError as e:
    print('empty', str(e))
try:
    [1].pop(9)
except IndexError as e:
    print('index', str(e))
'''


def build(directory, source, general):
    path = Path(directory, 'p.py')
    path.write_text(source, encoding='utf-8')
    exe = Path(directory, 'exe_g' if general else 'exe_d')
    if exe.exists():
        exe.unlink()
    env = dict(os.environ, AIL_NO_CACHE='1', AIL_QUIET_FALLBACK='1')
    env.pop('AIL_UNIFIED_FORCE', None)
    if general:
        env['AIL_UNIFIED_FORCE'] = '1'
    done = subprocess.run([sys.executable, '-B', str(CLI), 'compile', str(path),
                           '--syntax', 'python', '-o', str(exe)],
                          cwd=directory, capture_output=True, text=True, timeout=300, env=env)
    return done, exe


def cpython(directory, source):
    path = Path(directory, 'ref.py')
    path.write_text(source, encoding='utf-8')
    return subprocess.run([sys.executable, str(path)], cwd=directory,
                          capture_output=True, text=True, timeout=120)


def last_line(text):
    lines = text.strip().splitlines()
    return lines[-1] if lines else ''


@unittest.skipUnless(HAVE_CC, 'needs a C compiler')
class DeleteIndexMessage(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='ail-pre272-')
        self.dir = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def run_both(self, source):
        expected = cpython(self.dir, source)
        for general in (False, True):
            built, exe = build(self.dir, source, general)
            where = 'general' if general else 'default'
            self.assertEqual(built.returncode, 0, where + ':\n' + built.stdout + built.stderr)
            ran = subprocess.run([str(exe)], capture_output=True, text=True, timeout=120)
            yield where, expected, ran

    def test_uncaught_delete_message_names_assignment(self):
        for source in UNCAUGHT:
            for where, expected, ran in self.run_both(source):
                self.assertEqual(ran.returncode, expected.returncode, where + '\n' + source)
                self.assertEqual(ran.stdout, expected.stdout, where + '\n' + source)
                actual = last_line(ran.stderr)
                want = last_line(expected.stderr)
                if actual.startswith('IndexError: '):
                    actual = actual[len('IndexError: '):]
                if want.startswith('IndexError: '):
                    want = want[len('IndexError: '):]
                self.assertEqual(actual, want, where + '\n' + source)

    def test_caught_delete_text_and_routes_match(self):
        for where, expected, ran in self.run_both(CAUGHT):
            self.assertEqual(ran.returncode, expected.returncode, where + ':\n' + ran.stderr)
            self.assertEqual(ran.stdout, expected.stdout, where)

    def test_caught_delete_without_reading_text(self):
        for where, expected, ran in self.run_both(CAUGHT_NO_TEXT):
            self.assertEqual(ran.returncode, expected.returncode, where + ':\n' + ran.stderr)
            self.assertEqual(ran.stdout, expected.stdout, where)

    def test_in_range_delete_and_pop_are_unchanged(self):
        for where, expected, ran in self.run_both(IN_RANGE):
            self.assertEqual(ran.returncode, expected.returncode, where + ':\n' + ran.stderr)
            self.assertEqual(ran.stdout, expected.stdout, where)


if __name__ == '__main__':
    unittest.main()
