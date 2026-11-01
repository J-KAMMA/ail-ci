"""Typed reach for eight real programs: `list[list[bool]]` now compiles (job-prog8).

The hot function of `lab/census/programs/gdev/g09_012.py` is `count_palindromic_substrings`
(79% of its own time): a dynamic-programming table `dp: list[list[bool]]`.  The nested-list pass
only knew `int`, `float`, `str` and struct rows, so it refused the annotation; without the
annotation the bool/int mix was refused by boolkind.  A bool row is now a hidden
`_AilRow_bool` whose `list[bool]` field boolkind rewrites to the int spelling, exactly like a flat
`list[bool]`, so element reads still print `True`/`False` and a number stored into a bool row is
still refused (or keeps the general path) instead of silently printing `1`/`0`.

The oracle is CPython running the same source.  The probe program covers a local, a parameter and
a result, printing a row / the whole grid / a single element, aliasing a row, negative indexes,
an empty grid, a comprehension-built grid and a bool passed through a call.  The last case stores
an int into a bool row and must still match CPython (the general path, or a named refusal).
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


if __name__ == '__main__':
    unittest.main()
