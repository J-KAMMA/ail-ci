"""Typed reach, batch 7: the hot functions of eight real programs, against CPython 3.12.

`lab/census/programs/gdev/g10_032.py` spends its time in `largest_region`, an eight-direction BFS
over a `list[list[int]]`.  It used to fall to the general path twice over:

* its `visited = [[False] * cols ...]` row is a list of bools, while the grid's rows are lists of
  numbers.  `boolkind` keys a field by (class, name) and the generated row classes `_AilRow_bool`
  and `_AilRow_int` both call their element list `v`; an element store through `visited[r]` reached
  both classes, so `v` looked mixed.  `nested_lists` now types a bool row separately (bool is a
  scalar), and `boolkind` resolves `visited[r]` to `_AilRow_bool` from the list's own type, so the
  two fields never mix.
* `for dr, dc in directions:` iterates a tuple of constant tuple displays, which the tuple lowering
  refused.  It now builds the same list of items before the loop (a tuple of constants is immutable
  and evaluates the same way each time), but only when the program already needs the tuple lowering
  for another reason, so a program whose only tuple use is such a loop keeps its general-path C.

T1  `largest_region` and its program take the typed path, including the empty / one-cell / line /
    all-ones / diagonal boundaries, with CPython's stdout and exit code.
T2  a loop over a tuple of constant displays is typed, with break / continue and nested unpacking.
T3  an empty tuple, a tuple of mixed element types, a tuple used as a value, and a tuple of names
    stay correct (refused by name or built on the general path), never a wrong answer.
T4  a bool row and an int row in one function keep printing as CPython does.
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

G10 = '''from collections import deque


GRID: list[list[int]] = [
    [1, 1, 0, 0, 1, 0, 0, 0],
    [1, 0, 0, 1, 1, 0, 1, 0],
    [0, 0, 0, 1, 0, 0, 1, 1],
    [1, 1, 0, 0, 0, 1, 0, 1],
    [1, 0, 1, 1, 0, 1, 1, 0],
    [0, 0, 0, 1, 0, 0, 0, 0],
    [1, 1, 0, 1, 1, 1, 0, 1],
    [0, 1, 0, 0, 0, 1, 1, 1],
]


def largest_region(grid: list[list[int]]) -> int:
    if not grid or not grid[0]:
        return 0
    rows = len(grid)
    cols = len(grid[0])
    visited = [[False] * cols for _ in range(rows)]
    best = 0
    directions = ((-1, 0), (1, 0), (0, -1), (0, 1))
    for r in range(rows):
        for c in range(cols):
            if grid[r][c] != 1 or visited[r][c]:
                continue
            visited[r][c] = True
            queue: deque[tuple[int, int]] = deque([(r, c)])
            size = 0
            while queue:
                cr, cc = queue.popleft()
                size += 1
                for dr, dc in directions:
                    nr, nc = cr + dr, cc + dc
                    if (
                        0 <= nr < rows
                        and 0 <= nc < cols
                        and grid[nr][nc] == 1
                        and not visited[nr][nc]
                    ):
                        visited[nr][nc] = True
                        queue.append((nr, nc))
            best = max(best, size)
    return best


def main() -> None:
    print(f"Largest connected region of ones: {largest_region(GRID)}")


if __name__ == "__main__":
    main()
'''

G10_CASES = G10.split('def main() -> None:\n')[0] + '''def main() -> None:
    print(largest_region([]))
    print(largest_region([[]]))
    print(largest_region([[0]]))
    print(largest_region([[1]]))
    print(largest_region([[1, 1, 1, 1]]))
    print(largest_region([[1], [1], [1]]))
    print(largest_region([[0, 0], [0, 0]]))
    print(largest_region([[1, 0, 1], [0, 1, 0], [1, 0, 1]]))
    print(largest_region([[1, 1, 0], [1, 1, 0], [0, 0, 1]]))
    print(largest_region([[1, 1, 1], [1, 0, 1], [1, 1, 1]]))


main()
'''

TUPLE_LOOP = '''def total_dirs() -> int:
    directions = ((-1, 0), (1, 0), (0, -1), (0, 1))
    total = 0
    for dr, dc in directions:
        if dr == 0:
            continue
        total += dr * 10 + dc
    return total


def stop_loop() -> int:
    pairs = ((1, 2), (3, 4), (5, 6))
    out = 0
    for a, b in pairs:
        out += a * b
        if a == 3:
            break
    return out


def direct() -> int:
    out = 0
    for a, b in ((7, 8), (9, 10)):
        out += a + b
    return out


def words() -> str:
    parts = (("ab", "cd"), ("ef", "gh"))
    out = ""
    for a, b in parts:
        out += a + b
    return out


def main() -> None:
    print(total_dirs())
    print(stop_loop())
    print(direct())
    print(words())


main()
'''

TUPLE_VALUE = '''def main() -> None:
    directions = ((-1, 0), (1, 0), (0, -1), (0, 1))
    print(directions[0], len(directions))
    total = 0
    for dr, dc in directions:
        total += dr * 10 + dc
    print(total)
    a, b = ((5, 6), (7, 8))
    print(a, b)


main()
'''

TUPLE_NAMES = '''def main() -> None:
    a = 2
    b = 3
    pairs = ((a, b), (b, a))
    print(len(pairs), pairs[0])
    total = 0
    for x, y in pairs:
        total += x * y
    print(total, a, b)
    a = 10
    print(total, a, b)


main()
'''

TUPLE_EMPTY = '''def main() -> None:
    out = 0
    for x in ():
        out += 1
    print(out)


main()
'''

TUPLE_MIXED = '''def main() -> None:
    out = 0
    for v in (1, "two", 3.0):
        out += 1
    print(out)


main()
'''

BOOL_ROWS = '''from collections import deque


def scan(grid: list[list[int]]) -> str:
    rows = len(grid)
    cols = len(grid[0])
    seen = [[False] * cols for _ in range(rows)]
    q = deque([(0, 0)])
    out = ""
    while q:
        r, c = q.popleft()
        if seen[r][c]:
            continue
        seen[r][c] = True
        out += f"{grid[r][c]}"
        if c + 1 < cols:
            q.append((r, c + 1))
        if r + 1 < rows:
            q.append((r + 1, c))
    return out


def main() -> None:
    print(scan([[1, 2], [3, 4]]))
    print(scan([[9]]))


main()
'''


def compile_default(directory, text, name):
    source, exe = Path(directory, name + '.py'), Path(directory, name + '_x')
    source.write_text(text, encoding='utf-8')
    env = dict(os.environ, AIL_NO_CACHE='1')
    for key in ('AIL_NO_GENERAL', 'AIL_UNIFIED_FORCE', 'AIL_QUIET_FALLBACK'):
        env.pop(key, None)
    res = subprocess.run([sys.executable, '-B', str(ROOT / 'ail_chatgpt.py'), 'compile', source.name, '-o', exe.name],
                         cwd=directory, capture_output=True, text=True, timeout=900, env=env)
    return res, exe, source


def typed(res):
    return 'built on the general path' not in res.stderr


@unittest.skipUnless(HAVE_CC, 'needs a C compiler')
class Prog7(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.mkdtemp(prefix='prog7_')

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def build(self, text, name, expect_typed=True):
        res, exe, source = compile_default(self.tmp, text, name)
        self.assertEqual(res.returncode, 0, res.stderr[-1500:])
        if expect_typed is not None:
            self.assertEqual(typed(res), expect_typed, res.stderr[-600:])
        return exe, source

    def same(self, exe, source):
        want = subprocess.run([sys.executable, str(source)], capture_output=True, timeout=300)
        got = subprocess.run([str(exe)], capture_output=True, timeout=300)
        self.assertEqual(got.stdout, want.stdout)
        self.assertEqual(got.returncode, want.returncode)

    def check(self, text, name, expect_typed=True):
        exe, source = self.build(text, name, expect_typed)
        self.same(exe, source)

    def test_g10_hot_function_typed_and_equal(self):
        self.check(G10, 'g10', True)

    def test_g10_boundaries_typed_and_equal(self):
        self.check(G10_CASES, 'g10_cases', True)

    def test_constant_tuple_iteration_typed_and_equal(self):
        self.check(TUPLE_LOOP, 'tuple_loop', True)

    def test_tuple_used_as_a_value_stays_correct(self):
        self.check(TUPLE_VALUE, 'tuple_value', None)
        self.check(TUPLE_NAMES, 'tuple_names', None)

    def test_empty_and_mixed_tuples_stay_correct(self):
        self.check(TUPLE_EMPTY, 'tuple_empty', None)
        self.check(TUPLE_MIXED, 'tuple_mixed', None)

    def test_bool_row_and_int_row_in_one_function(self):
        self.check(BOOL_ROWS, 'bool_rows', True)


if __name__ == '__main__':
    unittest.main()
