"""More constructs that sent LLM-written programs to the general path, now built on the typed path.

Each test builds a program with the typed path alone (AIL_NO_GENERAL=1) under AIL_IR=0 and AIL_IR=1 and
compares it with CPython 3.12; a shape that stays refused on the typed path is refused by name there and
the default build (the general path) prints what CPython prints.

T1  print(xs) / f"{xs}" / f"{xs!r}" of a flat list of ints, floats or strs (a name, a field-free
    expression, a function's result); a list of bools stays refused
T2  Sequence[T] / Iterable[T] / Collection[T] parameters and results (typing or collections.abc), read
    as list[T]; a caller passing a tuple stays refused
T3  module-level list / tuple tables (of tuples, of lists, of objects) read by functions, passed to a
    helper that only reads them; a table of lists built by more than one function stays refused
T4  module-level type aliases (`Grid = list[list[int]]`, `X: TypeAlias = ...`, `type X = ...`)
T5  Sequence[tuple[...]] parameters, and bisect results inside tuples
T6  a tuple assignment with element targets (`a[i], a[j] = a[j], a[i]`)
"""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent
CLI = str(ROOT / 'ail_chatgpt.py')


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='ail-typed-blockers2-')
        self.dir = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def cpython(self, source, stdin=''):
        path = self.dir / 'cpython_main.py'
        path.write_text(source, encoding='utf-8')
        return subprocess.run([sys.executable, '-B', str(path)], input=stdin.encode(), capture_output=True, timeout=120)

    def build(self, source, ir='0', typed=False):
        entry = self.dir / 'main.py'
        entry.write_text(source, encoding='utf-8')
        exe = self.dir / ('out_ir%s_%s' % (ir, 'typed' if typed else 'default'))
        if exe.exists():
            exe.unlink()
        env = dict(os.environ, AIL_IR=ir)
        env.pop('AIL_NO_GENERAL', None)
        if typed:
            env['AIL_NO_GENERAL'] = '1'
        built = subprocess.run([sys.executable, '-B', CLI, 'compile', str(entry), '--syntax', 'python', '-o', str(exe)],
                               cwd=self.dir, capture_output=True, text=True, timeout=900, env=env)
        return built, exe

    def same(self, source, typed=False, irs=('0', '1'), stdin=''):
        """Built (on the typed path alone, or by default), the program prints what CPython prints and exits alike."""
        expected = self.cpython(source, stdin)
        for ir in irs:
            built, exe = self.build(source, ir, typed)
            self.assertEqual(built.returncode, 0, 'AIL_IR=%s: %s' % (ir, built.stderr))
            ran = subprocess.run([str(exe)], input=stdin.encode(), capture_output=True, timeout=120)
            self.assertEqual(ran.stdout.decode(), expected.stdout.decode(), 'AIL_IR=%s' % ir)
            self.assertEqual(ran.returncode, expected.returncode, 'AIL_IR=%s' % ir)
            if expected.returncode:
                last = expected.stderr.decode().strip().splitlines()[-1].split(':')[0]
                self.assertIn(last, ran.stderr.decode(), 'AIL_IR=%s' % ir)
        return expected.stdout.decode()

    def typed(self, source, stdin=''):
        return self.same(source, typed=True, stdin=stdin)

    def refused(self, source, *needles, irs=('0', '1')):
        """The typed path refuses by name (exit 3, no traceback)."""
        for ir in irs:
            built, _ = self.build(source, ir, typed=True)
            self.assertEqual(built.returncode, 3, 'AIL_IR=%s: %s' % (ir, built.stdout + built.stderr))
            self.assertNotIn('Traceback', built.stderr)
            for needle in needles:
                self.assertIn(needle, built.stderr)

    def both(self, source, *needles, stdin=''):
        """Refused on the typed path, and the default build prints what CPython prints."""
        self.refused(source, *needles, irs=('0',))
        return self.same(source, stdin=stdin)


LIST_TEXT = '''
def evens(n: int) -> list[int]:
    return [i for i in range(n) if i % 2 == 0]


def halves(n: int) -> list[float]:
    return [i / 2 for i in range(n)]


def names(n: int) -> list[str]:
    return ["n" + str(i) for i in range(n)]


def show(xs: list[int], fs: list[float], ss: list[str]) -> None:
    print(xs)
    print("fs:", fs, "end", sep="|")
    print(f"ss={ss} n={len(ss)} r={ss!r} s={ss!s}")


def main() -> None:
    xs: list[int] = [1, -2, 3, 9223372036854775807, -9223372036854775807 - 1]
    fs: list[float] = [1.5, 2.0, 1e20, 1e-7, float("inf"), -float("inf"), -0.0, 0.1 + 0.2, 1e16, 123456789.125]
    ss: list[str] = ["a", "b'c", 'd"e', "\\n\\t\\\\", "\\u00e9", "", "it's \\"x\\"", "\\x7f\\u2028", "\\U0001f600"]
    show(xs, fs, ss)
    print(evens(7))
    print(f"{evens(3)} and {halves(3)}")
    print(names(3), halves(2), end="!\\n")
    for k in range(3):
        print(k, evens(k))
    e: list[str] = []
    print(e, [], sorted([3, 1, 2]), list(range(4)), [x * x for x in range(4)])
    words = "the quick brown fox".split()
    print(words, sorted(words))
    print(f"{words[1:]}")
    big = list(range(2000))
    print(len(str(len(big))), f"{big}"[-12:])


main()
'''

BOOL_LIST = '''
def main() -> None:
    flags = [True, False, 3 > 2]
    print(flags)


main()
'''


class ListTextTests(Base):
    def test_flat_lists_print_like_cpython(self):
        self.typed(LIST_TEXT)

    def test_a_list_of_bools_stays_on_the_general_path(self):
        self.both(BOOL_LIST, 'print() given a list[int]')


SEQUENCES = '''
from collections.abc import Iterable, Sequence
from typing import Collection


def mean(xs: Sequence[float]) -> float:
    return sum(xs) / len(xs)


def longest(words: Iterable[str]) -> str:
    best = ""
    for w in words:
        if len(w) > len(best):
            best = w
    return best


def show(xs: Sequence[int], n: Collection[str]) -> None:
    print(xs, len(n), xs[-1], 4 in xs)


def rows(m: Sequence[Sequence[int]]) -> int:
    return sum(len(r) for r in m)


def evens(n: int) -> Sequence[int]:
    return [i for i in range(n) if i % 2 == 0]


def main() -> None:
    fs = [1.5, 2.25, 3.0]
    print(mean(fs))
    print(longest(["a", "abc", "ab"]))
    show([3, 4, 5], ["x"])
    ev = evens(9)
    print(ev)
    print(rows([[1, 2], [3]]))


main()
'''

SEQUENCE_TUPLE_ARGUMENT = '''
from typing import Sequence


def total(xs: Sequence[int]) -> int:
    return sum(xs)


def main() -> None:
    print(total((1, 2, 3)))


main()
'''

ABC_AS_VALUE = '''
from collections.abc import Sequence


def kind(x: object) -> str:
    return "seq" if isinstance(x, Sequence) else "other"


def main() -> None:
    print(kind([1]), kind(3))


main()
'''


class SequenceTests(Base):
    def test_read_only_sequence_annotations(self):
        self.typed(SEQUENCES)

    def test_a_tuple_argument_stays_on_the_general_path(self):
        self.both(SEQUENCE_TUPLE_ARGUMENT)

    def test_an_abc_used_as_a_value_keeps_its_import(self):
        self.refused(ABC_AS_VALUE, 'collections.abc', irs=('0',))


TABLES = '''
from dataclasses import dataclass


@dataclass
class Rec:
    name: str
    score: float


ROMAN: list[tuple[int, str]] = [(1000, "M"), (900, "CM"), (500, "D"), (400, "CD"), (100, "C"), (90, "XC"),
                                (50, "L"), (40, "XL"), (10, "X"), (9, "IX"), (5, "V"), (4, "IV"), (1, "I")]
DIRS = ((0, 1), (1, 0), (0, -1), (-1, 0))
GRID: list[list[int]] = [[1, 2, 3], [4, 5, 6]]
RECS = [Rec("ann", 3.5), Rec("bob", 1.25), Rec("cy", 2.0)]
READINGS = [(25.5, "C"), (77.0, "F")]


def to_roman(n: int) -> str:
    out = ""
    for value, sym in ROMAN:
        while n >= value:
            out += sym
            n -= value
    return out


def neighbours(x: int, y: int) -> int:
    total = 0
    for dx, dy in DIRS:
        total += (x + dx) * (y + dy)
    return total + len(DIRS) + DIRS.index((1, 0)) + DIRS[2][1]


def grid_sum(grid: list[list[int]]) -> int:
    return sum(sum(row) for row in grid)


def best(recs: list[Rec]) -> str:
    b = recs[0]
    for r in recs:
        if r.score > b.score:
            b = r
    return b.name


def total_of(rows: list[list[int]]) -> int:
    return grid_sum(rows)


class Printer:
    def __init__(self, prefix: str) -> None:
        self.prefix = prefix

    def show(self, n: int) -> str:
        return self.prefix + to_roman(n) + str(len(ROMAN))


def main() -> None:
    print(to_roman(1994), to_roman(3888))
    print(neighbours(3, 4))
    GRID[0][0] = 10
    print(grid_sum(GRID), total_of(GRID), GRID[1][2], len(GRID))
    print(best(RECS), RECS[1].score, len(RECS))
    for r in RECS:
        print(r.name)
    p = Printer("> ")
    print(p.show(14), p.show(9))
    for t, unit in READINGS:
        print(t, unit)


if __name__ == "__main__":
    main()
'''

GRID_TWO_BUILDERS = '''
GRID = [[1, 2], [3, 4]]


class Board:
    def __init__(self, n: int) -> None:
        self.n = n

    def cell(self) -> int:
        return GRID[0][0] + self.n


def main() -> None:
    GRID[0][0] = 9
    b = Board(1)
    print(b.cell(), GRID[0][0])


main()
'''

TABLE_PASSED_TO_A_WRITER = '''
EDGES = [(1, 2), (2, 3)]


def grow(edges: list[tuple[int, int]]) -> None:
    edges.append((3, 4))


def count() -> int:
    return len(EDGES)


def main() -> None:
    grow(EDGES)
    print(count(), EDGES)


main()
'''


TABLE_PASSED_TO_A_READER = '''
EDGES = [(1, 2), (2, 3), (3, 1)]


def degree(edges: list[tuple[int, int]], v: int) -> int:
    return sum(1 for a, b in edges if a == v or b == v)


def main() -> None:
    print(degree(EDGES, 1), degree(EDGES, 3), len(EDGES))
    for a, b in EDGES:
        print(a, b)


main()
'''


class TableTests(Base):
    def test_module_level_list_and_tuple_tables(self):
        self.typed(TABLES)

    def test_a_list_of_lists_built_twice_stays_on_the_general_path(self):
        self.both(GRID_TWO_BUILDERS, 'GRID')

    def test_a_table_handed_to_a_function_that_changes_it(self):
        # kept as number columns, the list was rebuilt for grow(): the append was lost (DIFFERENCES C68)
        self.both(TABLE_PASSED_TO_A_WRITER, 'EDGES')

    def test_a_number_tuple_table_handed_to_a_reader(self):
        self.typed(TABLE_PASSED_TO_A_READER)


ALIASES = '''
from typing import List, Optional, TypeAlias

Grid = list[list[int]]
Row: TypeAlias = List[int]
Board = list[Row]
type Name = str
Pair = tuple[int, str]
MaybeInt = Optional[int]


def total(g: Grid) -> int:
    return sum(sum(r) for r in g)


def first(b: Board) -> Row:
    return b[0]


def greet(n: Name) -> Name:
    return "hi " + n


def pair_text(p: list[Pair]) -> str:
    out = ""
    for a, b in p:
        out += str(a) + b
    return out


def main() -> None:
    g: Grid = [[1, 2], [3, 4]]
    print(total(g))
    print(first(g))
    print(greet("bob"))
    print(pair_text([(1, "a"), (2, "b")]))


main()
'''

ALIAS_AS_VALUE = '''
Grid = list[list[int]]


def main() -> None:
    g: Grid = [[1], [2]]
    print(Grid, len(g))


main()
'''


class AliasTests(Base):
    def test_type_aliases_in_annotations(self):
        self.typed(ALIASES)

    def test_an_alias_used_as_a_value_is_left_as_written(self):
        self.refused(ALIAS_AS_VALUE, 'Grid', irs=('0',))


TUPLE_SEQUENCES = '''
from bisect import bisect_left, bisect_right
from typing import Sequence


def sort_scores(records: Sequence[tuple[str, int]]) -> list[tuple[str, int]]:
    return sorted(records, key=lambda r: (-r[1], r[0]))


def find_first_last(values: list[int], target: int) -> tuple[int, int] | None:
    first = bisect_left(values, target)
    if first == len(values) or values[first] != target:
        return None
    last = bisect_right(values, target) - 1
    return first, last


def main() -> None:
    data = [("bob", 3), ("amy", 5), ("cat", 3)]
    for name, score in sort_scores(data):
        print(name, score)
    print(find_first_last([1, 2, 4, 4, 4, 7], 4), find_first_last([1, 2], 5))


main()
'''


class TupleSequenceTests(Base):
    def test_sequence_of_tuples_and_bisect(self):
        self.typed(TUPLE_SEQUENCES)


SWAPS = '''
from dataclasses import dataclass


@dataclass
class Box:
    a: int
    b: int


def bubble(arr: list[int]) -> list[int]:
    a = list(arr)
    n = len(a)
    for i in range(n):
        for j in range(n - 1 - i):
            if a[j] > a[j + 1]:
                a[j], a[j + 1] = a[j + 1], a[j]
    return a


def main() -> None:
    print(bubble([5, 3, 9, -1, 0]))
    w = ["x", "y", "z"]
    w[0], w[1], w[2] = w[1], w[2], w[0]
    print(w)
    fs = [1.5, 2.5]
    fs[0], fs[1] = fs[1], fs[0]
    print(fs)
    i = 0
    xs = [10, 20, 30]
    i, xs[i] = 2, 99
    print(i, xs)
    bx = Box(1, 2)
    bx.a, xs[0] = bx.b, bx.a
    print(bx.a, bx.b, xs)
    g = [[1, 2], [3, 4]]
    g[0][1], g[1][0] = g[1][0], g[0][1]
    print(g[0][1], g[1][0])
    try:
        xs[0], xs[5] = 1, 2
    except IndexError as exc:
        print("IndexError", exc, xs)


main()
'''


class SwapTests(Base):
    def test_element_swaps(self):
        self.typed(SWAPS)


if __name__ == '__main__':
    unittest.main()
