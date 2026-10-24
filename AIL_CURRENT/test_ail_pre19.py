# -*- coding: utf-8 -*-
"""pre19: `del` with a constant index or slice bound that overflows int64 is refused by name.

The first still-differing case recorded after pre7 is `del a[2**63 - 1]`: the final value fits
in an AIL int64, but the expression computes `2**63` first, so both builds trapped
"integer overflow" while CPython raises IndexError.  Constant slice bounds such as
`del a[2**100:2**101]` had the same cause and could delete nothing in CPython.  The value is
known at compile time, so the construct is refused there on both paths.  In-range constants and
the same overflowing expression outside a `del` are untouched.
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
    'a = [1, 2, 3]\nprint(a)\ndel a[2**63 - 1]\nprint(a)\n',
    'a = [1, 2, 3]\nprint(a)\ndel a[-2**63]\nprint(a)\n',
    'a = [1, 2, 3]\nprint(a)\ndel a[2**100000]\nprint(a)\n',
    'a = [1, 2, 3]\nprint(a)\ndel a[2**100:2**101]\nprint(a)\n',
    'a = [[1, 2], [3]]\nprint(a)\ndel a[0][2**63 - 1]\nprint(a)\n',
)
IN_RANGE = 'a = list(range(6))\nprint(a)\ndel a[1 + 1]\nprint(a)\ndel a[-2:-1]\nprint(a)\n'
NOT_A_DELETE = 'a = 2**63 - 1\nprint(a)\n'


def build(directory, source, general):
    path = Path(directory, 'p.py')
    path.write_text(source, encoding='utf-8')
    exe = Path(directory, 'exe_g' if general else 'exe_d')
    env = dict(os.environ, AIL_NO_CACHE='1', AIL_QUIET_FALLBACK='1')
    env.pop('AIL_UNIFIED_FORCE', None)
    if general:
        env['AIL_UNIFIED_FORCE'] = '1'
    return subprocess.run([sys.executable, '-B', str(CLI), 'compile', str(path),
                           '--syntax', 'python', '-o', str(exe)],
                          cwd=directory, capture_output=True, text=True, timeout=300, env=env), exe


@unittest.skipUnless(HAVE_CC, 'needs a C compiler')
class DeleteBoundBeyondInt64(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='ail-pre19-')
        self.dir = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def test_constant_bound_that_overflows_int64_is_refused_by_name(self):
        for source in REFUSED:
            for general in (False, True):
                built, _ = build(self.dir, source, general)
                where = 'general' if general else 'default'
                self.assertNotEqual(built.returncode, 0, where + ' built:\n' + source)
                text = built.stdout + built.stderr
                self.assertIn('64-bit signed integer range of an AIL int', text, where)
                self.assertIn('del ', text, where)

    def test_representable_constant_bounds_still_build_and_match(self):
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

    def test_same_expression_outside_a_delete_is_not_refused(self):
        for general in (False, True):
            built, _ = build(self.dir, NOT_A_DELETE, general)
            where = 'general' if general else 'default'
            self.assertEqual(built.returncode, 0, where + ':\n' + built.stdout + built.stderr)


if __name__ == '__main__':
    unittest.main()
