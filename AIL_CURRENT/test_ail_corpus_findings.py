"""Differences from CPython 3.12 found by an LLM-written program corpus, each compared with CPython (AIL_IR=0 and 1).

1. `v = v[:18]` on a list (the slice was built into the destination after it was cleared: length 0).
2. a @dataclass instance prints as `Row(a=1, word='x')` (print / repr / str / f-string / inside containers).
3. `op in ("size", "peek")` (and `x in t` with t a tuple) on the general path.
4. `heapq.nlargest/nsmallest(k, d.items(), key=lambda kv: kv[1])` over tuple elements.
5. `ch in it` with `it = iter(s)` consumes the iterator like CPython.
6. a class with __iter__/__next__ in for / list() / sum() / zip() / next().
7. `rest = data[1:]` over a list of str (was a C compile error).
8. a function returning tuple[int, int, list[list[int]]] (was a Python TypeError inside the compiler).
9. a module-level name bound twice (was "duplicate AIL name").
"""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent

SELF_SLICE = r'''import sys
def main() -> None:
    a = [x * 2 for x in range(10)]
    a = a[2:7]
    print(a)
    a = a[::-1]
    print(a)
    a = a[1:]
    print(a, len(a))
    s = sys.stdin.read().split()
    s = s[1:]
    print(s)
    s = s[:2]
    print(s)
    g = [[1, 2], [3], [4, 5, 6]]
    g = g[1:]
    print(g)
    f = [1.5, 2.5, 3.5]
    f = f[:2]
    print(f)
    for i in range(3):
        a = a[1:]
        print(a)
    b = [1, 2, 3, 4]
    c = b
    b = b[1:]
    print(b, c)
main()
'''
SELF_SLICE_IN = 'a b c d e\n'

SELF_SLICE_MIN = r'''def main() -> None:
    values = list(range(44))
    values = values[:18]
    print(len(values))
    v2 = list(range(10))
    v2 = v2[:18]
    print(len(v2))
    v3 = list(range(10))
    v3 = v3[:5]
    print(len(v3))

main()
'''
SELF_SLICE_MIN_IN = ''

DATACLASS_REPR = r'''from dataclasses import dataclass, field


@dataclass
class Row:
    a: int
    word: str


@dataclass
class Pt:
    x: float
    y: float = 0.5
    tags: list = field(default_factory=list)
    ok: bool = True
    n: object = None


@dataclass
class Box:
    rows: list
    best: Row
    names: dict


@dataclass(frozen=True)
class Fz:
    k: str


def main() -> None:
    r = Row(1, "x")
    print(r)
    print(repr(Row(2, "it's")))
    print(str(r), f"{r}", f"{r!r}", "%s %r" % (r, r))
    print([r, Row(3, "z")])
    print({"k": r})
    print((r, 1))
    p = Pt(1.0)
    p.tags.append("q")
    print(p)
    print(Pt(2.5, 3.0, [1, 2], False, "s"))
    b = Box([r, Row(4, "w")], r, {"a": Row(5, "v")})
    print(b)
    print([b])
    print(Fz("k"), [Fz("a")])
    r.a = 42
    print(r)
    print(Row(-1, "") , Row(10**12, "\n"))


main()
'''
DATACLASS_REPR_IN = ''

STR_IN_TUPLE = r'''def pair(a: int) -> tuple[int, str]:
    return a, "x"

def f(op: str, n: int) -> None:
    t = ("size", "peek")
    print(op in t, op not in t, "z" in t)
    u = (1, 2, 3)
    print(n in u, n not in u)
    print(op in ("size", "peek"), op not in ("size", "peek"))
    print(n in (1, 2), n not in (1, 2), n in (n + 1, n))
    print([c for c in ("a", "b", "c") if c in ("b", "c")])
    p = pair(n)
    print(p, "x" in p, 1 in p, 7 in p)
    k = "peek"
    print(op in (k, "q"), op in (op,))
    if op in ("size", "peek") and n in (1, 2):
        print("hit")
    print(op in ("a" + "b", "size"))

f("size", 1)
f("zz", 5)
'''
STR_IN_TUPLE_IN = ''

STR_IN_TUPLE_MIN = r'''def f(op: str) -> None:
    if op in ("size", "peek"):
        print("hit")

f("size")
'''
STR_IN_TUPLE_MIN_IN = ''

NLARGEST_KEY = r'''import heapq
import sys
from heapq import nsmallest


def main() -> None:
    totals: dict[str, float] = {}
    counts: dict[str, int] = {}
    for name in sys.stdin.read().split():
        totals[name] = totals.get(name, 0.0) + 1.5
        counts[name] = counts.get(name, 0) + 1
    items = list(totals.items())
    print(heapq.nlargest(2, items, key=lambda kv: kv[1]))
    print(heapq.nsmallest(2, items, key=lambda kv: (kv[1], kv[0])))
    print(heapq.nlargest(2, counts.items(), key=lambda kv: (kv[1], kv[0])))
    print(nsmallest(1, counts.items(), key=lambda kv: kv[1]))
    print(heapq.nlargest(2, counts.items()))
    print(heapq.nlargest(2, counts.values()))
    print(heapq.nsmallest(2, [5, 3, 9, 1], key=lambda x: -x))
    print(heapq.nlargest(3, [5, 3, 9, 1]))
    pairs = [(3, "c"), (1, "a"), (2, "b")]
    print(heapq.nsmallest(2, pairs, key=lambda p: p[0]))
    print(heapq.nlargest(2, pairs))
    for k, v in heapq.nlargest(2, counts.items(), key=lambda kv: kv[1]):
        print(k, v)


main()
'''
NLARGEST_KEY_IN = 'a b a c c c d a\n'

NLARGEST_MIN = r'''import heapq
import sys

def main() -> None:
    totals: dict[str, float] = {}
    for name in sys.stdin.read().split():
        totals[name] = totals.get(name, 0.0) + 1.5
    items = list(totals.items())
    top = heapq.nlargest(1, items, key=lambda kv: kv[1])
    print(top)

main()
'''
NLARGEST_MIN_IN = 'a b a\n'

IN_ITERATOR = r'''def sub(s: str, t: str) -> bool:
    it = iter(s)
    return all(ch in it for ch in t)


def firstn(xs: list[int]) -> None:
    it = iter(xs)
    print(3 in it)
    print(next(it))
    print(9 in it)
    print(list(it))
    print(1 in it)


print(sub("abcde", "ace"), sub("abc", "ba"), sub("", ""), sub("abc", ""), sub("", "a"))
firstn([1, 2, 3, 4, 5])
d = {"a": 1, "b": 2}
di = iter(d)
print("b" in di, "a" in di)
print(2 in iter(range(5)), 7 in iter(range(5)))
'''
IN_ITERATOR_IN = ''

USER_ITERATOR = r'''class Count:
    def __init__(self, n: int) -> None:
        self.n = n
        self.i = 0

    def __iter__(self):
        return self

    def __next__(self) -> int:
        if self.i >= self.n:
            raise StopIteration
        self.i += 1
        return self.i


class Bag:
    def __init__(self, xs: list) -> None:
        self.xs = xs

    def __iter__(self):
        print("iter called")
        return iter(self.xs)


class Walker:
    def __init__(self, xs: list) -> None:
        self.xs = xs
        self.k = 0

    def __next__(self) -> str:
        if self.k >= len(self.xs):
            raise StopIteration
        self.k += 1
        return self.xs[self.k - 1]


class Coll:
    def __init__(self, xs: list) -> None:
        self.xs = xs

    def __iter__(self):
        return Walker(self.xs)


def main() -> None:
    for x in Count(3):
        print(x)
    c = Count(4)
    for x in c:
        if x == 2:
            break
    print("after break", c.i)
    for x in c:
        print("rest", x)
    print(list(Count(5)), sum(Count(4)), max(Count(3)), sorted(Count(3)))
    print([x * 2 for x in Count(3)])
    for i, x in enumerate(Count(2)):
        print(i, x)
    for a, b in zip(Count(3), Count(2)):
        print(a, b)
    for x in Bag([7, 8]):
        print(x)
    print(list(Bag([1, 2])))
    for s in Coll(["a", "b"]):
        print(s)
    print(list(Coll(["p", "q"])))
    k = Count(2)
    print(next(k), next(k))
    try:
        next(k)
    except StopIteration:
        print("stop")
    print(next(Count(1)))
    it = Count(3)
    total = 0
    for x in it:
        total += x
    print(total)
    print(sum(x for x in Count(4)))
    print(any(x > 2 for x in Count(3)), all(x > 0 for x in Count(3)))
    print(set(Count(3)))


main()
'''
USER_ITERATOR_IN = ''

SLICE_STR_LIST = r'''import sys
data = sys.stdin.read().split()
coords = data[1:]
print(len(coords), coords[0])
'''
SLICE_STR_LIST_IN = '4 5 6\n'

TUPLE_RETURN = r'''import sys
def read_grid(text: str) -> tuple[int, int, list[list[int]]]:
    lines = text.splitlines()
    h, w = map(int, lines[0].split())
    digits = [int(ch) for line in lines[1:] for ch in line if "0" <= ch <= "9"]
    if len(digits) < h * w:
        raise ValueError("grid has fewer digits than expected")
    grid = [digits[i * w:(i + 1) * w] for i in range(h)]
    return h, w, grid
def prefix_sums(grid: list[list[int]]) -> list[list[int]]:
    h = len(grid)
    w = len(grid[0])
    P = [[0] * (w + 1) for _ in range(h + 1)]
    for i in range(h):
        prev, cur = P[i], P[i + 1]
        running = 0
        for j in range(w):
            cur[j + 1] = prev[j + 1] + running
    return P
def rect_sum(P: list[list[int]], r0: int, c0: int, r1: int, c1: int) -> int:
    return P[r1][c1] - P[r0][c1] - P[r1][c0] + P[r0][c0]
def main() -> None:
    h, w, grid = read_grid(sys.stdin.read())
    P = prefix_sums(grid)
    total = rect_sum(P, 0, 0, h, w)
    print(total)
if __name__ == "__main__":
    main()
'''
TUPLE_RETURN_IN = '5 3\n967\n688\n782\n648\n173\n'

MODULE_REBIND = r'''def total(values: list[int]) -> int:
    s = 0
    for v in values:
        s += v
    return s


values = [1, 2, 3]
print(total(values))
values = [10, 20]
print(total(values), len(values))
count = 0
for v in values:
    count += v
count = count * 2
print(count)
name = "a"
name = name + "b"
print(name)
'''
MODULE_REBIND_IN = ''


CASES = [
    ('self_slice_list', SELF_SLICE, SELF_SLICE_IN),
    ('self_slice_min', SELF_SLICE_MIN, SELF_SLICE_MIN_IN),
    ('dataclass_repr', DATACLASS_REPR, DATACLASS_REPR_IN),
    ('str_in_tuple_literal', STR_IN_TUPLE, STR_IN_TUPLE_IN),
    ('str_in_tuple_min', STR_IN_TUPLE_MIN, STR_IN_TUPLE_MIN_IN),
    ('nlargest_key_lambda', NLARGEST_KEY, NLARGEST_KEY_IN),
    ('nlargest_min', NLARGEST_MIN, NLARGEST_MIN_IN),
    ('in_on_iterator', IN_ITERATOR, IN_ITERATOR_IN),
    ('user_iterator_class', USER_ITERATOR, USER_ITERATOR_IN),
    ('slice_copy_str_list', SLICE_STR_LIST, SLICE_STR_LIST_IN),
    ('tuple_return_grid', TUPLE_RETURN, TUPLE_RETURN_IN),
    ('module_rebind', MODULE_REBIND, MODULE_REBIND_IN),
]


def build_and_run(directory, text, stdin, name, ir):
    source, exe = Path(directory, name + '.ail'), Path(directory, name)
    source.write_text(text, encoding='utf-8')
    env = dict(os.environ, AIL_IR='1' if ir else '0')
    built = subprocess.run([sys.executable, '-B', str(ROOT / 'ail_chatgpt.py'), 'compile', source.name,
                            '--syntax', 'python', '-o', exe.name], cwd=directory, capture_output=True,
                           text=True, timeout=600, env=env)
    expected = subprocess.run([sys.executable, str(source)], input=stdin.encode(), capture_output=True, timeout=60)
    if built.returncode != 0:
        return built, None, expected
    return built, subprocess.run([str(exe)], input=stdin.encode(), capture_output=True, timeout=60), expected


class CorpusFindings(unittest.TestCase):
    def check(self, slug, text, stdin, ir):
        with tempfile.TemporaryDirectory() as directory:
            built, ran, expected = build_and_run(directory, text, stdin, slug + ('_ir' if ir else ''), ir)
            self.assertEqual(expected.returncode, 0, expected.stderr)
            self.assertEqual(built.returncode, 0, built.stdout + built.stderr)
            self.assertEqual((ran.returncode, ran.stdout), (expected.returncode, expected.stdout), ran.stderr)

    def test_all_cases_default(self):
        for slug, text, stdin in CASES:
            with self.subTest(slug):
                self.check(slug, text, stdin, False)

    def test_all_cases_ir(self):
        for slug, text, stdin in CASES:
            with self.subTest(slug):
                self.check(slug, text, stdin, True)


if __name__ == '__main__':
    unittest.main()
