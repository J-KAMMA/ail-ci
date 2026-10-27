# -*- coding: utf-8 -*-
"""pre329: an uncaught nested-list deletion keeps CPython's IndexError text.

The pre307 reviewer recorded that on the default build an uncaught deletion into a nested list
printed just ``IndexError`` when a ``try`` was open but did not catch it.  The runtime trap was
converted to a catchable exception without its message, so the re-raised exception had empty
text.  The conversion now keeps the trap's message, so the uncaught line is CPython's
``IndexError: list assignment index out of range``.  The same cause is checked through an
argument, a class attribute, a dict value, an alias and an empty inner list.
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

UNCAUGHT_NESTED = (
    'xs = [[1, 2], [3]]\n'
    'try:\n    del xs[0][9]\nexcept ValueError:\n    print("not here")\n',
    'xs = [[1, 2], [3]]\n'
    'try:\n    del xs[-1][-9]\nexcept ValueError:\n    print("not here")\n',
    'def drop(rows, i, j):\n    del rows[i][j]\n\n'
    'xs = [[1, 2], [3]]\n'
    'try:\n    drop(xs, 0, 9)\nexcept ValueError:\n    print("not here")\n',
    'class Box:\n    def __init__(self):\n        self.rows = [[1, 2], [3]]\n\n'
    'b = Box()\n'
    'try:\n    del b.rows[0][9]\nexcept ValueError:\n    print("not here")\n',
    'd = {"rows": [[1, 2], [3]]}\n'
    'try:\n    del d["rows"][0][9]\nexcept ValueError:\n    print("not here")\n',
    'rows = [[1, 2], [3]]\n'
    'alias = rows\n'
    'try:\n    del alias[0][9]\nexcept ValueError:\n    print("not here")\n',
    'xs = [[1, 2], []]\n'
    'try:\n    del xs[1][0]\nexcept ValueError:\n    print("not here")\n',
)

CAUGHT_NESTED = '''def attempt(rows, i, j):
    try:
        try:
            del rows[i][j]
        finally:
            pass
    except IndexError as e:
        print(type(e).__name__, repr(str(e)), e.args)

attempt([[1, 2], [3]], 0, 9)
attempt([[]], 0, 0)
attempt([[1, 2], [3]], -1, -9)

class Box:
    def __init__(self):
        self.rows = [[1, 2], [3]]

box = Box()
attempt(box.rows, 0, 9)
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
class NestedDeleteMessage(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='ail-pre329-')
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

    def test_uncaught_nested_delete_keeps_index_message(self):
        for source in UNCAUGHT_NESTED:
            for where, expected, ran in self.run_both(source):
                self.assertEqual(ran.returncode, expected.returncode, where + '\n' + source)
                self.assertEqual(ran.stdout, expected.stdout, where + '\n' + source)
                self.assertEqual(last_line(ran.stderr), last_line(expected.stderr),
                                 where + '\n' + source)

    def test_caught_nested_delete_keeps_message_and_args(self):
        for where, expected, ran in self.run_both(CAUGHT_NESTED):
            self.assertEqual(ran.returncode, expected.returncode, where + ':\n' + ran.stderr)
            self.assertEqual(ran.stdout, expected.stdout, where)


if __name__ == '__main__':
    unittest.main()
