"""Typed reach for three hot program functions in the eight prog8 programs (job-prog8).

* `lab/census/programs/gdev/g09_012.py` -- `count_palindromic_substrings` (81% of its own time)
  uses a dynamic-programming table `dp: list[list[bool]]`.  The nested-list pass only knew `int`,
  `float`, `str` and struct rows, so it refused the annotation; without the annotation the
  bool/int mix was refused by boolkind.  A bool row is now a hidden `_AilRow_bool` whose
  `list[bool]` field boolkind rewrites to the int spelling, exactly like a flat `list[bool]`, so
  element reads still print `True`/`False` and a number stored into a bool row is still refused
  (or keeps the general path) instead of silently printing `1`/`0`.
* `lab/census/programs/gdev/g03_020.py` -- `simple_moving_average` computes `sum(values[:window])`.
  A slice of a `list[float]` was refused by the fold, which lost the float element type through
  the slice; it now sees the slice's base list and keeps a `double` accumulator.
* `lab/census/programs/gdev/g05_014.py` -- `first_non_repeating` walks `enumerate(text)` over a
  str, which was refused as "this use of a str as an iterable".  The enumerate loop now builds the
  same UTF-8 walk as `for ch in text:`, with a separate counter so the index counts characters.

The oracle is CPython running the same source.  The inline programs cover the boundaries of each
new path (local / parameter / attribute / list item / dict value, aliasing, negative indexes, empty
sequences, slices and unicode) and the last bool case stores an int into a bool row and must still
match CPython (the general path, or a named refusal).  The two real programs are compiled from the
tree itself, so the hot functions are exercised in place.
"""
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent
HAVE_CC = shutil.which('gcc') is not None or shutil.which('cc') is not None

PALINDROME = '''from typing import List


def count_palindromic_substrings(s: str) -> int:
    n: int = len(s)
    if n == 0:
        return 0

    dp: List[List[bool]] = [[False] * n for _ in range(n)]
    count: int = 0

    for length in range(1, n + 1):
        for i in range(0, n - length + 1):
            j: int = i + length - 1
            if s[i] == s[j] and (length <= 2 or dp[i + 1][j - 1]):
                dp[i][j] = True
                count += 1

    return count


def main() -> None:
    print(f"String: {'abaxyzzyxf'!r}")
    print(f"Number of palindromic substrings: {count_palindromic_substrings('abaxyzzyxf')}")
    print(f"String: {''!r}")
    print(f"Number of palindromic substrings: {count_palindromic_substrings('')}")
    print(f"String: {'a'!r}")
    print(f"Number of palindromic substrings: {count_palindromic_substrings('a')}")
    print(f"String: {'aaaa'!r}")
    print(f"Number of palindromic substrings: {count_palindromic_substrings('aaaa')}")


if __name__ == "__main__":
    main()
'''

BOOL_GRID = '''def build(n: int, flag: bool) -> list[list[bool]]:
    rows: list[list[bool]] = []
    for i in range(n):
        row: list[bool] = [flag] * n
        rows.append(row)
    rows[0][0] = not flag
    return rows


def count(rows: list[list[bool]]) -> int:
    total = 0
    for row in rows:
        for v in row:
            if v:
                total += 1
    return total


def main() -> None:
    dp: list[list[bool]] = [[i % 2 == 0 for i in range(4)] for _ in range(2)]
    dp[0][0] = False
    for i in range(2):
        for j in range(4):
            print(dp[i][j], end=" ")
        print()
    print(dp[1][2], dp[0][-1], sum(dp[0]), any(dp[1]))
    dp[1] = dp[0]
    dp[1][1] = False
    print(dp[0][1], dp[1][1])
    a = build(3, True)
    b = build(2, False)
    print(count(a), count(b), len(a[0]), a[0][0], b[1][1])
    empty: list[list[bool]] = []
    print(count(empty))
    empty.append([True, False])
    empty.append([False])
    print(empty[0][0], empty[0][1], empty[1][0], count(empty))


main()
'''

BOOL_ROW_NUMBER = '''def main() -> None:
    dp: list[list[bool]] = [[False] * 2 for _ in range(2)]
    dp[0][0] = 1
    print(dp)


main()
'''

FLOAT_SLICE = '''from dataclasses import dataclass
from math import sin


@dataclass
class Series:
    vals: list[float]


def slice_total(xs: list[float], a: int, b: int) -> float:
    return sum(xs[a:b])


def slice_min(xs: list[float], a: int, b: int) -> float:
    return min(xs[a:b])


def slice_max(xs: list[float], a: int, b: int) -> float:
    return max(xs[a:b])


def slice_scaled(xs: list[float], a: int, b: int) -> float:
    return sum(v * 0.5 for v in xs[a:b])


def main() -> None:
    xs: list[float] = [sin(i * 0.1) for i in range(8)]
    s = Series([0.5, 1.5, 2.5, 3.5])
    print(sum(xs[:3]), sum(xs[2:]), sum(xs[:]))
    print(sum(xs[-2:]), sum(xs[:-2]), sum(xs[2:100]), sum(xs[-100:3]))
    print(sum(s.vals[:2]), sum(s.vals[1:3]), sum(s.vals[::2]))
    print(min(xs[:3]), max(xs[3:]), min(s.vals[1:]), max(s.vals[:-1]))
    print(slice_total(xs, 1, 4), slice_min(xs, 0, 4), slice_max(xs, 1, 4), slice_scaled(xs, 1, 5))
    print(slice_min(s.vals, 0, 2), slice_max(s.vals, 2, 4), slice_scaled(s.vals, 2, 4))
    empty: list[float] = []
    print(len(empty[:]), len(empty[1:3]), len(xs[3:3]))


main()
'''

ENUM_STR = '''from dataclasses import dataclass


@dataclass
class Text:
    body: str


def indices(text: str) -> list[int]:
    out: list[int] = []
    for i, ch in enumerate(text):
        out.append(i)
    return out


def select(text: str, needle: str) -> list[int]:
    out: list[int] = []
    for i, ch in enumerate(text):
        if ch == needle:
            continue
        if i > 5:
            break
        out.append(i)
    return out


def nested(text: str) -> int:
    total = 0
    for i, a in enumerate(text):
        for j, b in enumerate(text):
            if i == j:
                total += 1
    return total


def decorate(text: str) -> str:
    acc = ""
    for i, ch in enumerate(text):
        ch = ch + "!"
        acc = acc + ch
    return acc


def main() -> None:
    print(indices(""))
    print(indices("abc"))
    print(indices("a\\u00e9\\u4e16z"))
    print(select("abcdefgh", "d"))
    print(select("abcdefgh", "a"))
    print(nested("ab\\u00e9"))
    print(decorate("ab"))
    texts: list[str] = ["xy", "z\\u00e9"]
    for i, ch in enumerate(texts[0]):
        print(i, ch, end="|")
    print()
    d: dict[str, str] = {"k": "m\\u00e9n"}
    for i, ch in enumerate(d["k"]):
        print(i, ch, end=";")
    print()
    t = Text("hello \\u4e16\\u754c")
    for i, ch in enumerate(t.body):
        print(i, ch, end="|")
    print()
    for i, ch in enumerate(t.body[:7]):
        print(i, ch, end=";")
    print()
    for i, ch in enumerate("x" + t.body[6:]):
        print(i, ch, end=",")
    print()


main()
'''


def compile_default(directory, text, name):
    source, exe, dbg = (Path(directory, name + '.py'), Path(directory, name + '_x'),
                        Path(directory, name + '_dbg'))
    source.write_text(text, encoding='utf-8')
    env = dict(os.environ, AIL_NO_CACHE='1')
    for key in ('AIL_NO_GENERAL', 'AIL_UNIFIED_FORCE', 'AIL_QUIET_FALLBACK'):
        env.pop(key, None)
    res = subprocess.run([sys.executable, '-B', str(ROOT / 'ail_chatgpt.py'), 'compile', source.name,
                          '--syntax', 'python', '-o', exe.name, '--debug-dir', str(dbg)],
                         cwd=directory, capture_output=True, text=True, timeout=900, env=env)
    c_file = dbg / 'program.c'
    return res, exe, (c_file.read_text(encoding='utf-8', errors='replace')
                      if c_file.exists() else '')


def run_cpython(directory, text, name):
    source = Path(directory, name + '_cpython.py')
    source.write_text(text, encoding='utf-8')
    return subprocess.run([sys.executable, str(source)], capture_output=True, text=True,
                          timeout=300, encoding='utf-8')


def typed(res):
    return 'built on the general path' not in res.stderr


@unittest.skipUnless(HAVE_CC, 'needs a C compiler')
class ProgramEight(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.mkdtemp(prefix='prog8_')

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def compare(self, text, name):
        res, exe, c_text = compile_default(self.tmp, text, name)
        self.assertEqual(res.returncode, 0, res.stderr[-2000:])
        want = run_cpython(self.tmp, text, name)
        got = subprocess.run([str(exe)], capture_output=True, text=True, timeout=300,
                             encoding='utf-8')
        self.assertEqual(got.stdout, want.stdout, name)
        self.assertEqual(got.returncode, want.returncode, name)
        return res, c_text

    def compare_tree_program(self, relative, name):
        path = ROOT.parent / relative
        if not path.exists():
            self.skipTest('%s is not in this tree' % relative)
        return self.compare(path.read_text(encoding='utf-8'), name)

    def test_palindrome_hot_function_is_typed(self):
        res, c_text = self.compare(PALINDROME, 'palindrome')
        self.assertTrue(typed(res), 'fell back to the general path: ' + res.stderr[-1000:])
        self.assertIn('count_palindromic_substrings', c_text)

    def test_nested_bool_rows_boundaries_are_typed(self):
        res, c_text = self.compare(BOOL_GRID, 'boolgrid')
        self.assertTrue(typed(res), 'fell back to the general path: ' + res.stderr[-1000:])
        self.assertIn('_AilRow_bool', c_text)

    def test_number_in_bool_row_still_matches_cpython(self):
        self.compare(BOOL_ROW_NUMBER, 'boolrow_number')

    def test_moving_average_float_slices_are_typed(self):
        res, c_text = self.compare_tree_program(
            'lab/census/programs/gdev/g03_020.py', 'moving_average')
        self.assertTrue(typed(res), 'fell back to the general path: ' + res.stderr[-1000:])
        self.assertIn('simple_moving_average', c_text)

    def test_float_list_slice_boundaries_are_typed(self):
        res, c_text = self.compare(FLOAT_SLICE, 'floatslice')
        self.assertTrue(typed(res), 'fell back to the general path: ' + res.stderr[-1000:])
        self.assertIn('slice_total', c_text)
        self.assertIn('double', c_text)

    def test_first_non_repeating_enumerate_str_is_typed(self):
        res, c_text = self.compare_tree_program(
            'lab/census/programs/gdev/g05_014.py', 'first_non_repeating')
        self.assertTrue(typed(res), 'fell back to the general path: ' + res.stderr[-1000:])
        self.assertIn('first_non_repeating', c_text)

    def test_enumerate_str_boundaries_are_typed(self):
        res, c_text = self.compare(ENUM_STR, 'enumstr')
        self.assertTrue(typed(res), 'fell back to the general path: ' + res.stderr[-1000:])
        self.assertIn('indices', c_text)


if __name__ == '__main__':
    unittest.main()
