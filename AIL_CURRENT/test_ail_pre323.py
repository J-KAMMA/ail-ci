# -*- coding: utf-8 -*-
"""pre323: a constant slice lower/upper bound outside int64 is clamped, not refused.

The rbrbrbpre7 review recorded `del a[2**63:]` as a pre-existing difference: both builds refused
it with `int64 constant out of range` while CPython's slice.indices() clamps the bound to the
sequence length and deletes nothing.  A constant lower/upper bound whose exact value leaves int64
is now rewritten to the nearest int64 bound, which selects exactly what CPython selects for a
list, tuple, str, bytes or bytearray, on reads, assignments and deletes, and through an argument,
a list item, an attribute and a dict value.  A step outside int64 is still refused by name, as is
a constant index outside int64.
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

MATCHING = {
    'del_start': 'a = [1, 2, 3]\nprint(a)\ndel a[2**63:]\nprint(a)\n',
    'del_stop': 'a = [1, 2, 3]\nprint(a)\ndel a[:2**63]\nprint(a)\n',
    'del_range': (
        'a = list(range(5))\n'
        'del a[2**63:2**64]\nprint(a)\n'
        'del a[-2**64:-2**63]\nprint(a)\n'
        'del a[-(2**63) - 1:2**63]\nprint(a)\n'),
    'read_types': (
        'xs = [10, 20, 30, 40]\n'
        'print(xs[2**63:])\nprint(xs[:2**63])\nprint(xs[-(2**63) - 1:2**63])\n'
        't = (10, 20, 30, 40)\nprint(t[2**63:])\nprint(t[:2**63])\n'
        's = "abcdef"\nprint(s[2**63:])\nprint(s[:2**63])\n'
        'b = b"abcdef"\nprint(b[2**63:])\nprint(b[:2**63])\n'
        'ba = bytearray(b"abcdef")\nprint(ba[2**63:])\nprint(ba[:2**63])\n'),
    'negative_step_slices': (
        'xs = list(range(6))\n'
        'print(xs[-2**63:])\nprint(xs[:-(2**63) - 1])\n'
        'print(xs[-(2**63) - 1:-(2**63) - 1])\n'
        'print(xs[2**63:-2**63])\nprint(xs[-2**63:2**63])\n'
        'print(xs[2**63::-1])\nprint(xs[:-(2**63) - 1:-1])\n'
        'print(xs[-(2**63) - 1:2**63:-1])\n'),
    'assign': (
        'xs = [1, 2, 3]\n'
        'xs[2**63:] = [9, 10]\nprint(xs)\n'
        'xs[:2**63] = [0]\nprint(xs)\n'
        'xs[-(2**63) - 1:2**63] = [7]\nprint(xs)\n'
        'del xs[2**63:]\nprint(xs)\n'
        'del xs[:-(2**63) - 1]\nprint(xs)\n'),
    'routes': (
        'def take(x):\n    return x\n'
        'a = [1, 2, 3, 4]\n'
        'print(take(a)[2**63:])\n'
        'print([a][0][2**63:])\n'
        'class C:\n    def __init__(self):\n        self.v = a\n'
        'c = C()\nprint(c.v[2**63:])\n'
        'print({0: a}[0][2**63:])\n'
        'print([1, 2, 3][:-(2**63) - 1])\n'),
    'empty_alias': (
        'xs = []\nys = xs\nprint(ys[2**63:])\n'
        'xs[2**63:] = [1]\nprint(xs, ys)\n'
        'del ys[:2**63]\nprint(xs, ys)\n'
        'zs = list(range(3))\nws = zs\nprint(ws[2**63:2**64])\n'
        'ws[2**63:2**64] = [8]\nprint(zs)\n'),
    'int64_boundaries': (
        'xs = list(range(5))\n'
        'print(xs[2**63 - 1:])\nprint(xs[:2**63 - 1])\n'
        'print(xs[-2**63:])\nprint(xs[:-2**63])\n'
        'print(xs[-2**63:2**63 - 1])\n'
        's = "abcde"\nprint(s[2**63 - 1:])\nprint(s[:2**63 - 1])\nprint(s[-2**63:])\n'),
    'in_range_cancellation': (
        'xs = list(range(8))\n'
        'print(xs[(2**63) * 0:])\nprint(xs[:(2**63) * 0])\n'
        'print(xs[(2**63) - (2**63):])\nprint(xs[::(2**63) // (2**62)])\n'),
}

REFUSED = {
    'huge_step': 'a = list(range(8))\nprint(a)\ndel a[::2**100]\nprint(a)\n',
    'huge_index': 'a = [1, 2, 3]\nprint(a)\ndel a[2**63]\nprint(a)\n',
}


def build(directory, source, general, name='p'):
    path = Path(directory, name + '.py')
    path.write_text(source, encoding='utf-8')
    exe = Path(directory, name + ('_g' if general else '_d'))
    env = dict(os.environ, AIL_NO_CACHE='1', AIL_QUIET_FALLBACK='1')
    env.pop('AIL_UNIFIED_FORCE', None)
    if general:
        env['AIL_UNIFIED_FORCE'] = '1'
    return subprocess.run([sys.executable, '-B', str(CLI), 'compile', str(path),
                           '--syntax', 'python', '-o', str(exe)],
                          cwd=directory, capture_output=True, text=True, timeout=300, env=env), exe


@unittest.skipUnless(HAVE_CC, 'needs a C compiler')
class SliceBoundsBeyondInt64(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='ail-pre323-')
        self.dir = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def test_constant_slice_bounds_match_cpython(self):
        for name, source in MATCHING.items():
            ref = Path(self.dir, name + '_ref.py')
            ref.write_text(source, encoding='utf-8')
            expected = subprocess.run([sys.executable, str(ref)], capture_output=True, timeout=60)
            for general in (False, True):
                where = '%s %s' % (name, 'general' if general else 'default')
                built, exe = build(self.dir, source, general, name)
                self.assertEqual(built.returncode, 0,
                                 where + ':\n' + built.stdout + built.stderr + '\n' + source)
                ran = subprocess.run([str(exe)], capture_output=True, timeout=60)
                self.assertEqual(ran.returncode, expected.returncode, where + '\n' + source)
                self.assertEqual(ran.stdout, expected.stdout, where + '\n' + source)

    def test_step_and_index_outside_int64_are_refused_by_name(self):
        for name, source in REFUSED.items():
            for general in (False, True):
                where = '%s %s' % (name, 'general' if general else 'default')
                built, _ = build(self.dir, source, general, name)
                self.assertNotEqual(built.returncode, 0, where + ' built:\n' + source)
                text = built.stdout + built.stderr
                self.assertIn('int64', text, where + ':\n' + text)
                self.assertNotIn('integer overflow', text, where)
                self.assertNotIn('internal error', text, where)


if __name__ == '__main__':
    unittest.main()
