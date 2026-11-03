"""A range() counter whose bounds are list elements stays an int64 loop counter.

I1  a list element and a struct-field list element bound the loop, default / forced general / exact
I2  a negative step and an empty range keep their CPython results
I3  the int64 boundary values still produce the CPython iteration counts
I4  an overflowing loop body stops loudly on the int64 paths and stays exact with --exact-int
I5  a list element beyond int64 drives an exact loop
I6  the default generated C has no tagged counter for an element-bounded loop
"""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from test_ail_int64_default import ROOT, build, env_for, run

CASES = r'''import sys


class Box:
    def __init__(self, xs, lo, hi):
        self.xs = xs
        self.lo = lo
        self.hi = hi


def list_bound(a: list[int], s: int) -> int:
    t = 0
    for j in range(a[s], a[s + 1]):
        t += a[j] + j
    return t


def field_bound(b: Box) -> int:
    t = 0
    for j in range(b.xs[b.lo], b.xs[b.hi]):
        t += j
    return t


def negative_step(a: list[int], s: int) -> int:
    t = 0
    for j in range(a[s], a[s + 1], -2):
        t += j
    return t


def empty(a: list[int], s: int) -> int:
    t = 0
    for j in range(a[s], a[s + 1]):
        t += 1
    return t + 7


def count(a: list[int], first: int, second: int) -> int:
    c = 0
    for j in range(first, second):
        c += 1
    return c


def count_down(a: list[int], first: int, second: int) -> int:
    c = 0
    for j in range(first, second, -2):
        c += 1
    return c


def main():
    a = [0, 1, 2, 3, 4, 5]
    print(list_bound(a, 1))
    print(list_bound(a, 2))
    print(field_bound(Box([0, 1, 4, 7, 11, 16], 1, 4)))
    b = [10, 1, 0]
    print(negative_step(b, 0))
    print(negative_step(b, 1))
    e = [5, 5, 10, 3]
    print(empty(e, 0))
    print(empty(e, 2))
    edge = [9223372036854775805, 9223372036854775807,
            -9223372036854775808, -9223372036854775808]
    print(count(edge, edge[0], edge[1]))
    print(count(edge, edge[2], edge[3]))
    print(count_down(edge, -9223372036854775806, -9223372036854775808))


main()
'''

OVERFLOW = r'''def boom(a: list[int]) -> int:
    t = 0
    for j in range(a[0], a[1]):
        t = j * j
    return t


print(boom([3037000500, 3037000501]))
'''

EXACT_BIG = r'''def total(a):
    t = 0
    for j in range(a[0], a[1]):
        t += j
    return t


print(total([2 ** 64, 2 ** 64 + 4]))
'''


class RangeElementBounds(unittest.TestCase):
    """I1-I4"""

    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.exe = {}
        for mode in ('default', 'force', 'exact'):
            made, exe = build(cls.tmp.name, CASES, 'cases', mode)
            if made.returncode:
                raise AssertionError('%s cases did not build: %s' % (mode, made.stderr[-2000:]))
            cls.exe[mode] = exe
        reference = {}
        exec(CASES.rsplit('\nmain()', 1)[0], reference)
        out = []
        import contextlib
        import io
        with contextlib.redirect_stdout(io.StringIO()) as captured:
            reference['main']()
        cls.want = captured.getvalue()

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_list_field_step_and_empty_bounds(self):
        for mode in ('default', 'force', 'exact'):
            code, out, err = run(self.exe[mode], '')
            self.assertEqual((code, out), (0, self.want), (mode, err))

    def test_overflow_is_loud_on_the_int64_paths(self):
        for mode in ('default', 'force'):
            with tempfile.TemporaryDirectory() as tmp:
                made, exe = build(tmp, OVERFLOW, 'overflow', mode)
                self.assertEqual(made.returncode, 0, made.stderr)
                code, out, err = run(exe, '')
            self.assertEqual((code, out), (1, ''), (mode, err))
            self.assertTrue(err.startswith('OverflowError: integer overflow in *'), (mode, err))

    def test_exact_mode_keeps_the_overflow_result(self):
        with tempfile.TemporaryDirectory() as tmp:
            made, exe = build(tmp, OVERFLOW, 'overflow', 'exact')
            self.assertEqual(made.returncode, 0, made.stderr)
            code, out, err = run(exe, '')
        self.assertEqual((code, out), (0, '%d\n' % (3037000500 ** 2)), err)

    def test_exact_mode_counts_beyond_int64(self):
        with tempfile.TemporaryDirectory() as tmp:
            made, exe = build(tmp, EXACT_BIG, 'exactbig', 'exact')
            self.assertEqual(made.returncode, 0, made.stderr)
            code, out, err = run(exe, '')
        want = sum(range(2 ** 64, 2 ** 64 + 4))
        self.assertEqual((code, out), (0, '%d\n' % want), err)

    def test_default_c_has_no_tagged_counter(self):
        with tempfile.TemporaryDirectory() as tmp:
            debug = Path(tmp, 'debug')
            made, _ = build(tmp, CASES, 'cshape', 'default', ('--debug-dir', str(debug)))
            self.assertEqual(made.returncode, 0, made.stderr)
            generated = Path(debug, 'program.c').read_text(encoding='utf-8')
        self.assertNotIn('ail_tint', generated)
        self.assertIn('for (int64_t', generated)
