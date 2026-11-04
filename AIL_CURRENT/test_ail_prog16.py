"""Typed reach for the hot functions of eight real programs (job prog16), against CPython 3.12.

The CPython hybrid accelerates only functions that reach the typed path, so this batch closes two
compiler gaps that kept whole programs (and every function in them) on the general path:

1. A comprehension whose target is a pair of names over `enumerate` (`[i for i, v in enumerate(xs)
   if ...]`): `_listcomp_kind` / `_listcomp_into_temp` only accepted a plain name target.  A pair
   over `enumerate` now reuses the existing pair plan (`_pair_plan`); the index and the element are
   bound as int locals.  An `enumerate(..., start=...)` stays refused by name, matching the
   pair-fold rules; a list of floats is already supported by the wider pair plan in this tree.
2. A module-level list of tuples with a negative float literal (`READINGS = [(25.0, "C"), (-40.0,
   "F")]`): `modtables._scalar` handled `-1` but not `-1.5`, so the table looked like a list of
   non-numbers and the typed path refused the program.  The table is now lowered like any other
   tuple table.

Both fixes take t268 and g25_038 from the general path to the typed path.  t068, t003 and g09_028
were already typed and stay so.  g21_034, g20_038 and g14_040 still need large features (Any /
Optional / list[dict] parameters, re.Pattern / re.Match, typing reflection); they are recorded in
lab/progfix/prog16.md and are not asserted here.

P1  the five typed programs compile with AIL_NO_GENERAL=1 on AIL_IR=0 and AIL_IR=1 and match CPython
P2  a pair comprehension over enumerate matches CPython through an argument, a list item and an
    attribute, over empty/duplicate/negative inputs and both builds
P3  a module table of tuples with negative floats (including -0.0) matches CPython on both builds
P4  the pair forms the compiler does not build are refused by name on the typed path and still match
    CPython on the default build (enumerate start)
"""
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parent
CLI = ROOT / 'ail_chatgpt.py'
HAVE_CC = shutil.which('gcc') is not None or shutil.which('cc') is not None

T268_INPUTS = [
    '',
    '\n',
    '0\n',
    '1 0\n',
    '5 4\n0 1\n1 2\n2 3\n3 4\n',
    '3 2\n0 1\n2 2\n',
    '4 5\n0 1\n1 2\n2 3\n3 0\n0 2\n',
    '2 1\n0 5\n',
]
T068_INPUTS = [
    '',
    'Hello, world! HELLO. Another; test...\nfoo bar foo\n',
    '... ; , . !\n\n',
    'one\nTwo\tTHREE\r\n',
]
T003_INPUTS = [
    '1\n5\n',
    '2\n1 2\n',
    '3\n3 1 2\n',
    '4\n3 1 4 2\n',
    '7\n-2 5 0 -9 5 5 1\n',
]

PAIRCOMP = '''from dataclasses import dataclass

@dataclass
class Box:
    values: list[int]


def above(xs: list[int], k: int) -> list[int]:
    return [i for i, v in enumerate(xs) if v >= k]


def every(xs: list[int]) -> list[int]:
    return [i for i, v in enumerate(xs)]


def main() -> None:
    vals = [5, -2, 0, 7, 7, -9, 3]
    print(above(vals, 0))
    print(above(vals, 7))
    print(above(vals, 100))
    print(every(vals))
    print(every([]))
    print(above([], 0))
    data = [[10, 20, 30], [4, 5]]
    print(above(data[1], 5))
    box = Box([9, 8, 7])
    print(above(box.values, 8))
    print([i * 2 + v for i, v in enumerate([2, 3, 4]) if i > 0])


main()
'''

NEGTABLE = '''from typing import Final

READINGS: Final[list[tuple[float, str]]] = [
    (25.0, "C"),
    (-40.0, "F"),
    (-0.0, "K"),
    (1.5, "X"),
    (-273.15, "C"),
]


def report() -> None:
    for value, unit in READINGS:
        print(value, unit, value * 2.0)
    print(READINGS[1][0], READINGS[2][0], READINGS[-1][0])


def total() -> float:
    t = 0.0
    for value, unit in READINGS:
        t += value
    return t


def main() -> None:
    report()
    print(total())


main()
'''

PAIR_START = '''def f(xs: list[int]) -> list[int]:
    return [i for i, v in enumerate(xs, start=1) if v > 0]


def main() -> None:
    print(f([1, 0, 2]))
    print(f([]))


main()
'''

PAIR_FLOAT = '''def f(xs: list[float], k: float) -> list[int]:
    return [i for i, v in enumerate(xs) if v > k]


def main() -> None:
    print(f([0.5, 2.5, -1.0], 0.0))
    print(f([], 1.0))


main()
'''

PAIR_NOARGS = '''def f() -> list[int]:
    return [i for i, v in enumerate()]


def main() -> None:
    print(f())


main()
'''


def run_python(path, stdin):
    return subprocess.run([sys.executable, str(path)], input=stdin.encode('utf-8'),
                          capture_output=True, timeout=300)


def build(source, directory, name, ir, typed):
    exe = Path(directory, name + '_ir%s_%s' % (ir, 'typed' if typed else 'default'))
    if exe.exists():
        exe.unlink()
    env = dict(os.environ, AIL_IR=str(ir), AIL_NO_CACHE='1')
    env.pop('AIL_UNIFIED_FORCE', None)
    env.pop('AIL_QUIET_FALLBACK', None)
    if typed:
        env['AIL_NO_GENERAL'] = '1'
    else:
        env.pop('AIL_NO_GENERAL', None)
    res = subprocess.run([sys.executable, '-B', str(CLI), 'compile', str(source), '--syntax', 'python',
                          '-o', str(exe)], cwd=directory, capture_output=True, text=True, timeout=900, env=env)
    return res, exe


@unittest.skipUnless(HAVE_CC, 'needs a C compiler')
class Prog16(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.mkdtemp(prefix='prog16_')
        cls.cache = {}

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def compiled(self, source, ir, typed, name):
        key = (str(source), ir, typed)
        if key not in self.cache:
            built, exe = build(source, self.tmp, name, ir, typed)
            self.assertEqual(built.returncode, 0, 'AIL_IR=%s typed=%s:\n%s' % (ir, typed, built.stdout + built.stderr))
            self.cache[key] = exe
        return self.cache[key]

    def same(self, source, stdin, irs=(0, 1), typed=True, name=None):
        want = run_python(source, stdin)
        for ir in irs:
            exe = self.compiled(source, ir, typed, name or Path(source).stem)
            got = subprocess.run([str(exe)], input=stdin.encode('utf-8'), capture_output=True, timeout=300)
            self.assertEqual(got.stdout, want.stdout, 'AIL_IR=%s stdin=%r' % (ir, stdin))
            self.assertEqual(got.returncode, want.returncode, 'AIL_IR=%s stdin=%r' % (ir, stdin))

    def refused_typed(self, source, *needles):
        """Refused by name; `needles` is one group of acceptable wordings."""
        for ir in (0, 1):
            built, _ = build(source, self.tmp, Path(source).stem, ir, typed=True)
            self.assertEqual(built.returncode, 3, 'AIL_IR=%s:\n%s' % (ir, built.stdout + built.stderr))
            self.assertNotIn('Traceback', built.stderr)
            self.assertTrue(any(needle in built.stderr for needle in needles), built.stderr)

    def inline(self, text, name):
        path = Path(self.tmp, name + '.py')
        path.write_text(text, encoding='utf-8')
        return path

    # P1 -- the five programs whose hot function is on the typed path
    def test_t268_pair_comprehension_program_typed(self):
        for stdin in T268_INPUTS:
            self.same(REPO / 'lab/census/programs/dev/t268.py', stdin, name='t268')

    def test_t068_stays_typed(self):
        for stdin in T068_INPUTS:
            self.same(REPO / 'lab/census/programs/dev/t068.py', stdin, name='t068')

    def test_t003_stays_typed(self):
        for stdin in T003_INPUTS:
            self.same(REPO / 'lab/corpus/programs/deepseek-v4.1-flash-free/t003.py', stdin, name='t003')

    def test_g09_stays_typed(self):
        self.same(REPO / 'lab/census/programs/gdev/g09_028.py', '', name='g09')

    def test_g25_negative_float_tuple_table_typed(self):
        self.same(REPO / 'lab/census/programs/gdev/g25_038.py', '', name='g25')

    # P2 -- the new comprehension form on its own
    def test_pair_comprehension_routes_and_boundaries(self):
        path = self.inline(PAIRCOMP, 'paircomp')
        self.same(path, '', name='paircomp')

    # P3 -- the new module table form on its own
    def test_negative_float_tuple_module_table(self):
        path = self.inline(NEGTABLE, 'negtable')
        self.same(path, '', name='negtable')

    # P4 -- the neighbouring forms stay either refused by name or equal to CPython
    def test_enumerate_without_iterable_is_refused_by_name(self):
        path = self.inline(PAIR_NOARGS, 'pairnoargs')
        for typed in (True, False):
            for ir in (0, 1):
                built, _ = build(path, self.tmp, 'pairnoargs', ir, typed)
                self.assertEqual(built.returncode, 3, 'typed=%s AIL_IR=%s:\n%s'
                                 % (typed, ir, built.stdout + built.stderr))
                self.assertNotIn('Traceback', built.stderr)
                self.assertIn('enumerate() with other than (iterable[, start])', built.stderr)

    def test_pair_start_in_comprehension_is_typed(self):
        # prog17: the pair plan now evaluates an `enumerate` start once (after the iterable) and
        # adds it with the overflow-checked `ck_add`, so this shape is built instead of refused.
        path = self.inline(PAIR_START, 'pairstart')
        self.same(path, '', name='pairstart')
        self.same(path, '', typed=False, name='pairstart_default')

    def test_pair_comprehension_over_floats_is_typed(self):
        path = self.inline(PAIR_FLOAT, 'pairfloat')
        self.same(path, '', name='pairfloat')


if __name__ == '__main__':
    unittest.main()
