# -*- coding: utf-8 -*-
"""pre19: `del` with a constant bound whose *exact final value* leaves int64 is refused by name.

CPython's int is unbounded, so a constant `del` index or slice step can pass through an
out-of-int64 intermediate and still name a valid element, e.g. `del a[2**63 * 0]` or
`del a[(10**20) // (10**19)]`.  The pre269 constant-index pass folds the whole expression and
range-checks only the final value; this helper follows the same rule.  A final index or step
value outside int64 (or a constant too large to fold) is refused at compile time on both paths.
A constant slice lower/upper bound outside int64 is clamped to the nearest int64 bound, exactly
what CPython's slice.indices() does after clamping to the sequence length (pre323).  Representable
boundaries such as `2**63 - 1` and `-2**63` still build and then behave like CPython (here an
IndexError at run time).
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
    'a = [1, 2, 3]\nprint(a)\ndel a[-2**63 - 1]\nprint(a)\n',
    'a = [1, 2, 3]\nprint(a)\ndel a[2**100000]\nprint(a)\n',
    'a = list(range(8))\nprint(a)\ndel a[::2**100]\nprint(a)\n',
    'a = [[1, 2], [3]]\nprint(a)\ndel a[0][2**63]\nprint(a)\n',
)
IN_RANGE = """a = [0, 1, 2, 3, 4]
del a[2**63 * 0]
print("del-zero", a)
a = [0, 1, 2, 3, 4]
del a[(1 << 63) >> 62]
print("del-shift", a)
a = list(range(20))
del a[(10**20) // (10**19)]
print("del-div", a)
a = [0, 1, 2, 3, 4]
del a[(1 << 63) - (1 << 63) + 3]
print("del-add", a)
a = [0, 1, 2, 3, 4]
del a[-(1 << 63) >> 62]
print("del-negative", a)
a = [1, 2, 3]
del a[2**100:2**101]
print("del-slice", a)
a = list(range(6))
print(a)
del a[1 + 1]
print(a)
del a[-2:-1]
print(a)
"""
REPRESENTABLE_EDGES = (
    'a = [1, 2, 3]\nprint(a)\ndel a[2**63 - 1]\nprint(a)\n',
    'a = [1, 2, 3]\nprint(a)\ndel a[-2**63]\nprint(a)\n',
)
NOT_A_DELETE = 'a = 2**63 - 1\nprint(a)\n'


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
                # This tree's earlier constant checks already refuse some of these cases by name
                # (`int64 index out of range` / `int64 constant out of range`); both sides' fixes
                # are kept, so accept either named refusal and never a run-time overflow trap.
                self.assertTrue(any(named in text for named in (
                    '64-bit signed integer range of an AIL int',
                    'int64 index out of range',
                    'int64 constant out of range',
                    'outside the signed 64-bit range',
                )), where + ':\n' + text)
                self.assertNotIn('integer overflow', text, where)
                if '64-bit signed integer range of an AIL int' in text:
                    self.assertIn('del ', text, where)

    def test_representable_constant_bounds_still_build_and_match(self):
        sources = [IN_RANGE] + list(REPRESENTABLE_EDGES)
        for index, source in enumerate(sources):
            ref = Path(self.dir, 'ref%d.py' % index)
            ref.write_text(source, encoding='utf-8')
            expected = subprocess.run([sys.executable, str(ref)], capture_output=True, timeout=60)
            for general in (False, True):
                built, exe = build(self.dir, source, general, 'p%d' % index)
                where = 'general' if general else 'default'
                self.assertEqual(built.returncode, 0,
                                 where + ':\n' + built.stdout + built.stderr)
                ran = subprocess.run([str(exe)], capture_output=True, timeout=60)
                self.assertEqual(ran.returncode, expected.returncode, where + ':\n' + source)
                self.assertEqual(ran.stdout, expected.stdout, where + ':\n' + source)

    def test_same_expression_outside_a_delete_is_not_refused(self):
        for general in (False, True):
            built, _ = build(self.dir, NOT_A_DELETE, general)
            where = 'general' if general else 'default'
            self.assertEqual(built.returncode, 0, where + ':\n' + built.stdout + built.stderr)


if __name__ == '__main__':
    unittest.main()
