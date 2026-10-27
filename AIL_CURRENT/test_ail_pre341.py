# -*- coding: utf-8 -*-
"""pre341: a module-level list of number tuples is not lowered when it is mutated.

`ps = [(1, 2), (3, 4)]` at module level was kept as two number columns, and every value use
rebuilt a fresh list (`_ail_rc_ps()`).  A module-level `del ps[-1]` therefore removed an element
from that temporary, so the list printed unchanged.  The same cause hid `append`, `pop`, an item
store and a mutation through an alias or a function argument.

The tuple pass now keeps such a list as written when a module-level statement does anything but
read it in place, and the normal compiler handles all of those shapes.  Read-only uses (`for`,
index, `len`, `print`) and tuple deletions inside a function still match CPython.
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

DELETE_PROGRAMS = (
    'ps = [(1, 2), (3, 4), (5, 6)]\ndel ps[-1]\nprint(ps)\n',
    'ps = [(1, 2), (3, 4), (5, 6)]\ndel ps[1]\nprint(ps)\n',
    'ps = [(1, 2), (3, 4), (5, 6)]\ndel ps[-2]\nprint(ps)\n',
    'ps = [(1, 2), (3, 4)]\ndel ps[0]\nprint(ps)\n',
    'ps = [(1.5, 2.5), (3.5, 4.5)]\ndel ps[-1]\nprint(ps)\n',
    'ps = [(1, 2), (3, 4)]\ntry:\n    del ps[9]\nexcept IndexError as e:\n'
    '    print(type(e).__name__, str(e))\nprint(ps)\n',
)

MUTATION_PROGRAMS = (
    'ps = [(1, 2), (3, 4)]\nps.append((5, 6))\nprint(ps)\n',
    'ps = [(1, 2), (3, 4)]\nps.pop()\nprint(ps)\n',
    'ps = [(1, 2), (3, 4)]\nps[0] = (9, 9)\nprint(ps)\n',
    'ps = [(1, 2), (3, 4)]\nq = ps\ndel q[0]\nprint(ps, q)\n',
    'ps = [(1, 2), (3, 4)]\nq = ps\nq.append((5, 6))\nprint(ps)\n',
    'ps = [(1, 2), (3, 4)]\ndef drop(xs):\n    del xs[-1]\ndrop(ps)\nprint(ps)\n',
)

READ_PROGRAMS = (
    'ps = [(1, 2), (3, 4), (5, 6)]\nfor p in ps:\n    print(p)\n',
    'ps = [(1, 2), (3, 4)]\nprint(ps, len(ps), ps[0], ps[-1], (3, 4) in ps)\n',
    'ps = [(1, 2), (3, 4)]\nprint(ps)\ndel ps[-1]\nprint(ps)\n',
    'ps = [(1, 2), (3, 4)]\nprint(sorted(ps), list(ps), set(ps))\n',
)


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
class ModuleTupleList(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='ail-pre341-')
        self.dir = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def compare_all(self, programs):
        for source in programs:
            expected = cpython(self.dir, source)
            for general in (False, True):
                built, exe = build(self.dir, source, general)
                where = 'general' if general else 'default'
                self.assertEqual(built.returncode, 0, where + ':\n' + built.stdout + built.stderr)
                ran = subprocess.run([str(exe)], capture_output=True, text=True, timeout=120)
                label = where + '\n' + source
                self.assertEqual(ran.returncode, expected.returncode, label)
                self.assertEqual(ran.stdout, expected.stdout, label)
                self.assertEqual(last_line(ran.stderr), last_line(expected.stderr), label)

    def test_module_tuple_delete_matches_cpython(self):
        self.compare_all(DELETE_PROGRAMS)

    def test_module_tuple_mutation_matches_cpython(self):
        self.compare_all(MUTATION_PROGRAMS)

    def test_module_tuple_reads_match_cpython(self):
        self.compare_all(READ_PROGRAMS)


if __name__ == '__main__':
    unittest.main()
