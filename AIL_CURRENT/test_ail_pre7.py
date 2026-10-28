# -*- coding: utf-8 -*-
"""pre7: `del` with a constant index outside int64 matches CPython.

With exact ints (bigint, BIGINT.md) `del a[2**63]` builds and raises CPython's IndexError
("cannot fit 'int' into an index-sized integer") like CPython, for both builds and for a nested
receiver too.  (It used to be refused by name when an int was a signed 64-bit value.)
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

REFUSED = (
    'a = [1, 2, 3]\nprint(a)\ndel a[2**63]\nprint(a)\n',
    'a = [1, 2, 3]\nprint(a)\ndel a[2**64]\nprint(a)\n',
    'a = [1, 2, 3]\nprint(a)\ndel a[-2**63 - 1]\nprint(a)\n',
    'a = [[1, 2], [3]]\nprint(a)\ndel a[0][2**63]\nprint(a)\n',
)
IN_RANGE = 'a = list(range(4))\nprint(a)\ndel a[1 + 1]\nprint(a)\n'


def build(directory, source, general):
    path = Path(directory, 'p.py')
    path.write_text(source, encoding='utf-8')
    exe = Path(directory, 'exe_g' if general else 'exe_d')
    exe.unlink(missing_ok=True)       # the CLI refuses to overwrite an existing output
    env = dict(os.environ, AIL_NO_CACHE='1', AIL_QUIET_FALLBACK='1')
    env.pop('AIL_UNIFIED_FORCE', None)
    if general:
        env['AIL_UNIFIED_FORCE'] = '1'
    return subprocess.run([sys.executable, '-B', str(CLI), 'compile', str(path),
                           '--syntax', 'python', '-o', str(exe)],
                          cwd=directory, capture_output=True, text=True, timeout=300, env=env), exe


@unittest.skipUnless(HAVE_CC, 'needs a C compiler')
class DeleteIndexBeyondInt64(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='ail-pre7-')
        self.dir = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def test_constant_index_outside_int64_is_refused_by_name(self):
        # exact ints (bigint): builds and matches CPython (stdout, exit code)
        for source in REFUSED:
            ref = Path(self.dir, 'ref.py')
            ref.write_text(source, encoding='utf-8')
            expected = subprocess.run([sys.executable, str(ref)], capture_output=True, timeout=60)
            for general in (False, True):
                built, exe = build(self.dir, source, general)
                where = 'general' if general else 'default'
                self.assertEqual(built.returncode, 0, where + ':\n' + source + built.stdout + built.stderr)
                ran = subprocess.run([str(exe)], capture_output=True, timeout=60)
                self.assertEqual((ran.stdout.replace(b'\r\n', b'\n'), ran.returncode),
                                 (expected.stdout.replace(b'\r\n', b'\n'), expected.returncode),
                                 where + ':\n' + source + ran.stderr.decode(errors='replace'))

    def test_representable_constant_index_still_builds_and_matches(self):
        ref = Path(self.dir, 'ref.py')
        ref.write_text(IN_RANGE, encoding='utf-8')
        expected = subprocess.run([sys.executable, str(ref)], capture_output=True, timeout=60)
        self.assertEqual(expected.returncode, 0)
        for general in (False, True):
            built, exe = build(self.dir, IN_RANGE, general)
            where = 'general' if general else 'default'
            self.assertEqual(built.returncode, 0, where + ':\n' + built.stdout + built.stderr)
            ran = subprocess.run([str(exe)], capture_output=True, timeout=60)
            self.assertEqual(ran.returncode, expected.returncode, where)
            self.assertEqual(ran.stdout, expected.stdout, where)


if __name__ == '__main__':
    unittest.main()
