"""Differences from CPython 3.12 found by a third LLM-style program corpus (150 new programs), each compared
with CPython (AIL_IR=0 and 1).

1. `a or b` / `a and b` used as a VALUE yielded the bool 0/1 instead of an operand: `h % 12 or 12` printed 1.
   Ints are now built as the operand (a temporary), every other operand kind is left to the general path.
2. a tuple local handed whole to a builtin that iterates it (`max(c)`, `sum(c)`, `list(c)`, `any(c)`,
   `" ".join(map(str, c))` ...) became a class instance and ended in `TypeError: 'instance' object is not iterable`.
3. `sorted(date.fromisoformat(s) for s in xs)` (a generator, not a list) compared the dates with `<` on the
   class (TypeError); the generator is now the bracketed comprehension for sorted / min / max / list.
4. `print(*f(x))`, `print(*xs)` for a list returned by a function, a generator or `reversed(xs)` was refused
   ("not statically known to be a list/tuple"); the value is walked into a fresh list.
5. math.comb, math.perm and math.lcm of two ints are built (refused before).
7. print(*xs) / print(label, *xs, sep=..., end=...) as a statement is a loop on the typed path.
8. a user __lt__ orders instances on the general path (min / max / sorted / tuples holding them), also for the
   datetimes held in (datetime, str) tuples; arithmetic on such an element is typed through the tuple.
9. the libm / wrapping helpers the typed path writes (_ail_c_atan2, wrapping_add) work on the general path.
10. itertools.combinations / permutations / zip_longest (two iterables) / combinations_with_replacement as values
    on the general path; math.fsum (list of floats), math.prod (list of ints), math.modf; textwrap.wrap / fill /
    dedent (default options; a hyphen or a tab uses CPython's wordsep / expandtabs rules); str.strip(chars) on the
    general path.
6. a lambda that only calls builtins (`key=lambda w: (len(w), w)`) was refused on the general path as "closing
   over a local variable (len)".
11. a comprehension inside a lambda is a scope of its own: `filter(lambda rec: all(key in rec for key in required),
    records)` was refused on the general path because `key` (the comprehension's own loop target) was read as an
    enclosing local, i.e. as a closure; only `required` is one, and it is captured.
12. `itertools.takewhile` / `dropwhile` with a predicate that reads a local (a closure) were refused on the general
    path: the raw-function-pointer callbacks of the C iterators carry no user data (`ail_it_takewhile` takes no
    `ud`), so the two functions are now the Python pieces `_ail_takewhile` / `_ail_dropwhile` of genlib.
13. `bytes.hex(sep[, bytes_per_sep])` (and the bytearray method) was refused on the general path ("accepts no
    arguments"); it is now the Python method `_ail_bm_hex` of the bytes prelude, with CPython 3.12's grouping
    (a positive group counts from the left, a negative one from the right, 0 is one group) and its errors.
14. `bisect.bisect(...)`: ail_syntax renames it to `bisect` (CPython's alias of bisect_right) but the general path
    did not know that name; `bisect` is now in the implicit library of pyboxed2 (`_lib_bisect = _lib_bisect_right`).
15. `max(a, *xs, key=...)` / `max(*xs)` / `min(...)` with a starred argument (beside other positional arguments)
    was refused on the general path; the arguments are expanded into one list, which max/min iterate -- a lone
    expanded argument is CPython's "iterate the single argument", and no argument at all is its TypeError.
16. `max` / `min` with `default=` and more than one positional argument is CPython's TypeError ("Cannot specify a
    default for max() with multiple positional arguments"), never a value -- the expansion above only learns the
    count at run time, so the refusal is emitted there; with two literal arguments it is decided at compile time.
17. `itertools.takewhile` / `dropwhile` open the iterable at CALL time (CPython's TypeError for a non-iterable is
    raised there, not on the first `next`): the pieces above are plain wrappers around the generator. A keyword
    call is refused by name, as CPython takes no keyword argument either.
"""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent

BOOLOP_VALUE = r"""def twelve(h: int) -> int:
    return h % 12 or 12


def first_nonzero(a: int, b: int, c: int) -> int:
    return a or b or c


def last_if_all(a: int, b: int, c: int) -> int:
    return a and b and c


def main() -> None:
    for h in (0, 1, 11, 12, 13, 16, 23):
        print(h, twelve(h), first_nonzero(h % 3, h % 4, 99), last_if_all(h % 3, h % 4, 7))
    total = 0
    for i in range(8):
        total += (i % 3 or 10) + (i % 2 and 5)
    print(total)
    k = 4
    flag = (k > 2) or (total < 0)
    print(flag, k and total, 0 or k)
    if k and total:
        print("both")
    s = "" or "dflt"
    t = "x" and "y"
    xs = [] or [1]
    print(s, t, xs, 0 or 7, 5 and 9)


main()
"""

TUPLE_WHOLE = r"""def main() -> None:
    a = 3
    for x in [1, 2]:
        c = (x, a * x)
        print(max(c), min(c), sum(c), list(c))
        print(any(c), all(c), list(reversed(c)), sorted(c))
        print(" ".join(map(str, c)), list(map(str, c)), list(enumerate(c)), dict(zip(c, c)))
        print(sum(c) / len(c), max(c) - min(c))
        a = max(c) + 1
    print(a)


main()
"""

DATE_GENEXP = r"""from datetime import date, timedelta


def main() -> None:
    lines = ["2020-01-05", "2019-03-01", "2021-07-09"]
    ds = sorted(date.fromisoformat(s) for s in lines)
    print(ds[0], ds[-1])
    print((ds[-1] - ds[0]).days, ds[0] + timedelta(days=100))
    first = min(date.fromisoformat(s) for s in lines)
    last = max(date.fromisoformat(s) for s in lines if s.strip())
    print(first, last, list(date.fromisoformat(s) for s in lines)[1])


main()
"""

PRINT_STAR = r"""def doubled(n: int) -> list[int]:
    return [i * 2 for i in range(n)]


def main() -> None:
    xs = doubled(4)
    print(*xs)
    print(*doubled(3))
    print(*(x + 1 for x in xs))
    print(*reversed(xs))
    print(*sorted(xs, reverse=True), sep=", ")
    print(*xs[1:], end="!\n")
    print(*"abc".split("b"))


main()
"""

MATH_INT = r"""import math
from math import comb, lcm, perm


def main() -> None:
    n = 12
    print(comb(n, 3), math.comb(n, 2) + math.perm(n, 3), comb(n, n // 2), comb(n, n + 1), comb(n, 0))
    print(perm(n, 0), perm(n, n + 1), perm(5, 5))
    print(lcm(n, 18), lcm(0, n), lcm(-4, 6), math.lcm(7, 3))
    print(comb(2 * n, n) // (n + 1), comb(60, 30))
    try:
        print(comb(-1, 2))
    except ValueError as e:
        print("ValueError", e)
    try:
        print(perm(3, -1))
    except ValueError as e:
        print("ValueError", e)


main()
"""

LAMBDA_BUILTINS = r"""def main() -> None:
    words = set("pear fig apple kiwi fig plum".split())
    for w in sorted(words, key=lambda w: (len(w), w)):
        print(f"{w:<12}{len(w):>3}")
    longest = max(words, key=lambda w: (len(set(w)), w))
    print(longest, min(words, key=lambda w: (-len(w), w)))
    print(sorted(words, key=lambda w: (abs(len(w) - 3), w)))


main()
"""

DIJKSTRA_CLOSURE = r"""import heapq


def main() -> None:
    q = t if (t := 3) else 2          # a walrus: this function is built on the general path
    data = [5, 3, 9, 1, 7, 4]
    heap: list[int] = []
    for x in data:
        heapq.heappush(heap, x * q)
    heapq.heapify(heap)
    order = []
    while heap:
        order.append(heapq.heappop(heap))
    base = 4
    dist = {v: abs(v - base * q) for v in order}
    far = max(order, key=lambda v: (dist[v], -v))
    near = min(order, key=lambda v: (dist[v] + base, v))
    print(order, far, near)
    print(sorted(order, key=lambda v: (abs(dist[v] - base), v)))
    print(list(map(lambda v: v + base, order)), list(filter(lambda v: v > base * q, order)))
    order.sort(key=lambda v: (v % base, v))
    print(order)


main()
"""

BASE_BUILTINS = r"""def main() -> None:
    q = t if (t := 3) else 2
    n = 37 + q
    print(bin(n), hex(n), oct(n), bin(n).count("1"), "a b".isspace(), "  ".isspace(), "".isspace(), q)


main()
"""

PRINT_STAR_STATEMENT = r"""def f(n: int) -> list[int]:
    return [i * 2 for i in range(n)]


def main() -> None:
    xs = f(4)
    words = "b a c".split()
    fs = [x / 4 for x in xs]
    e: list[int] = []
    print(*xs)
    print(*words, sep=", ")
    print(*fs, end="!\n")
    print("lbl", *xs)
    print("lbl", len(xs), *e)
    print(*e)
    print(*f(3), sep="")
    print(*sorted(words), sep="\n")
    for i in range(2):
        print("row", i, *xs[1:], sep="|")


if __name__ == "__main__":
    main()
"""

DT_TUPLE_ORDER = r"""from datetime import datetime


def main() -> None:
    lines = ["2024-05-04 01:37:40 a", "2023-01-02 10:00:00 b", "2025-03-04 11:11:11 c"]
    stamps: list[tuple[datetime, str]] = []
    for line in lines:
        ts = datetime.strptime(line[:19], "%Y-%m-%d %H:%M:%S")
        stamps.append((ts, line))
    first = min(stamps)
    last = max(stamps)
    print(first[1])
    print(last[1])
    print((last[0] - first[0]).days)
    print(sorted(stamps)[1][1])


if __name__ == "__main__":
    main()
"""

LT_DISPATCH = r"""class Ver:
    def __init__(self, major: int, minor: int) -> None:
        self.major = major
        self.minor = minor

    def __lt__(self, other: "Ver") -> bool:
        return (self.major, self.minor) < (other.major, other.minor)


class Sub(Ver):
    pass


def main() -> None:
    q = t if (t := 3) else 2
    vs = [Ver(1, 5), Sub(1, 2), Ver(0, 9), Ver(2, 0)]
    best = min(vs)
    worst = max(vs)
    print(best.major, best.minor, worst.major, worst.minor, q)
    for v in sorted(vs):
        print(v.major, v.minor)
    pairs = [(Ver(2, 1), "b"), (Ver(1, 1), "a")]
    first = min(pairs, key=lambda p: p[1])
    print(first[1], min(pairs)[1], sorted(pairs)[0][1])
    vs.sort(reverse=True)
    print(vs[0].major, Ver(1, 1) < Ver(1, 2), Ver(1, 2) > Ver(1, 1))


if __name__ == "__main__":
    main()
"""

INTRINSIC_LEAK = r"""import math
from math import hypot


def main() -> None:
    q = t if (t := 3) else 2
    pts = [(3, 4), (1, 1), (0, 5), (-2, 7)]
    pts.sort(key=lambda p: (math.atan2(p[1], p[0]), math.sqrt(p[0] ** 2 + p[1] ** 2)))
    print(pts, q)
    print(sorted(pts, key=lambda p: hypot(p[0], p[1])))
    print(max(pts, key=lambda p: (math.floor(p[1] / 2), p)))


if __name__ == "__main__":
    main()
"""

ITERTOOLS_LISTS = r"""from itertools import combinations, permutations, zip_longest
import itertools


def main() -> None:
    nums = [4, 7, 1, 9]
    print(list(combinations(nums, 2)))
    print(list(itertools.combinations("abc", 3)), list(combinations(nums, 0)), list(combinations(nums, 5)))
    print(list(permutations(nums[:3])))
    print(list(permutations("abc", 2)), list(permutations(nums, 0)), list(permutations([], 0)))
    print(list(zip_longest(nums, [1, 2])), list(zip_longest("ab", [1], fillvalue=0)))
    print(list(zip_longest([1], [2, 3], fillvalue="-")))
    total = 0
    for pair in combinations(nums, 2):
        total += pair[0] * pair[1]
    big = list(permutations(range(5)))
    print(total, len(big), big[17], len(list(combinations(range(20), 3))))
    print(sorted(set(sum(c) for c in combinations(nums, 3))))


if __name__ == "__main__":
    main()
"""

MODF = r"""import math


def main() -> None:
    frac, whole = math.modf(3.75)
    print(frac, whole)
    r = math.modf(-2.5)
    print(r[0], r[1], r)
    for x in [0.0, -0.0, 1e20, float("inf"), 5.0]:
        f, w = math.modf(x)
        print(f, w)


if __name__ == "__main__":
    main()
"""

TEXTWRAP_FSUM_PROD = r"""import math
import textwrap
from textwrap import fill


def show(lines: list[str]) -> None:
    for line in lines:
        print("[" + line + "]")


def main() -> None:
    text = "The quick brown fox jumps over the lazy dog and keeps running far away from here   with  extra   spaces"
    for w in [10, 20, 33, 80]:
        show(textwrap.wrap(text, w))
        print(textwrap.fill(text, width=w))
    print(fill("  leading spaces and a veryveryveryverylongwordthatneedsbreaking here", 12))
    show(textwrap.wrap("short", 70))
    show(textwrap.wrap("", 10))
    show(textwrap.wrap("   ", 10))
    show(textwrap.wrap("line one\nline two\n\nline three", 9))
    print(textwrap.dedent("    hello\n      world\n\n    again\n"))
    print(repr(textwrap.dedent("\t a\n\t b\n  \n\t  c")))
    print(repr(textwrap.dedent("  x\n y")))
    ones = [0.1] * 10
    xs = ones + [1e100, 1.0, -1e100]
    print(math.fsum(xs), sum(xs), math.fsum([0.1, 0.2, 0.3]), math.fsum([1e16, 1.0, 1.0, -1e16]))
    ys = [1e308, 1e308, -1e308]
    print(math.fsum(ys) if False else 0, math.fsum([2.5]), math.fsum([-0.0]), math.fsum(ones))
    print(math.prod([1, 2, 3, 4]), math.prod([7, 0, 9]))


if __name__ == "__main__":
    main()
"""

COMP_LAMBDA = r"""from typing import Any


def has_all_required_keys(record: dict[str, Any], required: tuple[str, ...]) -> bool:
    return all(key in record for key in required)


def filter_records(records: list[dict[str, Any]], required: tuple[str, ...]) -> list[dict[str, Any]]:
    return list(filter(lambda rec: all(key in rec for key in required), records))


def main() -> None:
    required: tuple[str, ...] = ("id", "name", "email")
    records: list[dict[str, Any]] = [
        {"id": 1, "name": "Alice", "email": "alice@example.com"},
        {"id": 2, "name": "Bob"},
        {},
        {"name": "Eve", "email": "eve@example.org", "id": 5},
    ]
    kept = filter_records(records, required)
    print(len(kept), kept[0]["name"], kept[1]["id"])
    dropped = [rec for rec in records if not has_all_required_keys(rec, required)]
    print(len(dropped), [sorted(rec) for rec in dropped])
    pairs = [(1, "a"), (2, "b"), (3, "c")]
    tags = ["x", "y"]
    print([p for p in pairs if any(p[0] == i + 1 for i in range(2))], tags)
    ranges = [n for n in range(6) if all(n != m for m in (0, 3))]
    print(ranges, sum(x for x in ranges if x > 2))


if __name__ == "__main__":
    main()
"""

WHILE_CLOSURE = r"""import itertools


def split_at_first_exceeding(values: list[int], threshold: int) -> tuple[list[int], list[int]]:
    prefix: list[int] = list(itertools.takewhile(lambda x: x <= threshold, values))
    rest: list[int] = list(itertools.dropwhile(lambda x: x <= threshold, values))
    return prefix, rest


def main() -> None:
    data: list[int] = [3, 8, 2, 7, 15, 4]
    threshold: int = 10
    prefix, rest = split_at_first_exceeding(data, threshold)
    print(prefix, rest)
    low, high = 2, 4
    print(list(itertools.takewhile(lambda v: low <= v <= high, [2, 3, 9])),
          list(itertools.dropwhile(lambda v: low <= v <= high, [2, 3, 9])))
    print(list(itertools.islice(itertools.takewhile(lambda v: v < threshold, itertools.count()), 3)))
    empty: list[int] = []
    print(list(itertools.takewhile(lambda v: v > 0, empty)), list(itertools.dropwhile(lambda v: v > 0, empty)))
    # a non-iterable is CPython's TypeError at CALL time, before anything iterates the result
    try:
        itertools.takewhile(lambda v: v < threshold, 5)
        print("no raise")
    except TypeError as e:
        print("TypeError", e)
    try:
        itertools.dropwhile(lambda v: v < threshold, None)
        print("no raise")
    except TypeError as e:
        print("TypeError", e)
    were = itertools.takewhile(lambda v: v < threshold, data)
    print(list(were))


if __name__ == "__main__":
    main()
"""

HEX_SEP = r"""def pack_bits(bits: list[bool]) -> bytes:
    out = bytearray()
    value = 0
    for i, bit in enumerate(bits):
        if bit:
            value |= 1 << (7 - i % 8)
        if i % 8 == 7:
            out.append(value)
            value = 0
    return bytes(out)


def show(data: bytes, sep: str) -> str:
    return data.hex(sep)


def main() -> None:
    bits: list[bool] = [True, False, True, True, False, False, False, True, True, True]
    packed: bytes = pack_bits(bits)
    print(packed.hex(), packed.hex(" "), packed.hex(":"))
    print(show(packed, "-"), bytearray(packed).hex(" "))
    print(packed.hex(" ", 2), packed.hex(" ", -2), packed.hex(":", 0), packed.hex(":", 100))
    print(b"".hex(":"), b"\x01".hex("ab" if False else ":"))
    table = {"x": b"\xde\xad\xbe\xef"}
    print(table["x"].hex("."))
    for sep in ("", "ab", 1):
        try:
            print(packed.hex(sep))
        except (TypeError, ValueError) as e:
            print(type(e).__name__, e)
    for group in (2147483648, -2147483649, 2147483647, -2147483648):
        try:
            print(packed.hex(":", group))
        except OverflowError as e:
            print(type(e).__name__, e)


if __name__ == "__main__":
    main()
"""

BISECT_MODULE = r"""import bisect


def describe(sorted_values: list[int], target: int) -> tuple[int, int, int]:
    left: int = bisect.bisect_left(sorted_values, target)
    right: int = bisect.bisect_right(sorted_values, target)
    return left, right, right - left


def main() -> None:
    xs: list[int] = [1, 3, 3, 5, 7]
    for target in (0, 1, 3, 4, 7):
        print(target, describe(xs, target), bisect.bisect(xs, target))
    preview: list[int] = xs.copy()
    bisect.insort(preview, 4)
    bisect.insort_left(preview, 3)
    bisect.insort_right(preview, 3)
    print(preview, preview.count(3))
    words: list[str] = ["ant", "bee", "cow"]
    print(bisect.bisect(words, "boo"), bisect.bisect_left(words, "ant"))
    print(bisect.bisect(xs, 3, 0, 2), bisect.bisect_right(xs, 9))
    print(bisect.bisect(xs, 3, lo=1, hi=4), bisect.bisect_right(xs, 3, hi=-1))
    for lo, hi in ((-1, 9), (0, 99), (0, -1), (5, 6), (0, -2), (2, 1)):
        try:
            print(bisect.bisect(xs, 3, lo, hi))
        except (ValueError, IndexError) as e:
            print(type(e).__name__, e)
    for lo, hi in ((-1, 9), (0, 99), (0, -1)):
        try:
            print(bisect.bisect_left(xs, 3, lo, hi))
        except (ValueError, IndexError) as e:
            print(type(e).__name__, e)
    try:
        bisect.insort(preview, 4, 0, 99)
    except IndexError as e:
        print(type(e).__name__, e)
    print(bisect.bisect_left(xs, 3, 0, None), bisect.bisect_right(xs, 3, hi=None))
    print(bisect.bisect(xs, 9, lo=1, hi=None), bisect.bisect_left([], 1, 0, None))
    bisect.insort_left(preview, 3, 0, None)
    bisect.insort_right(preview, 3, hi=None)
    print(preview)
    for bad in (1.5, "1", None, [0]):
        try:
            print(bisect.bisect_left(xs, 3, bad, None))
        except TypeError as e:
            print("lo", type(e).__name__, e)
    for bad in (1.5, "2", [0]):
        try:
            print(bisect.bisect_left(xs, 3, 0, bad))
        except TypeError as e:
            print("hi", type(e).__name__, e)
    try:
        print(bisect.bisect_left(xs, 3, -1, 1.0))
    except TypeError as e:
        print("order", type(e).__name__, e)


if __name__ == "__main__":
    main()
"""

STAR_MAX = r"""def widest(rows: list[tuple[str, int]]) -> int:
    return max(len("name"), *(len(name) for name, _ in rows))


def main() -> None:
    rows = [("ab", 1), ("abcd", 2)]
    print(widest(rows))
    xs = [3, 9, 2]
    print(max(*xs), min(*xs), max(0, *xs), min(xs[0], *xs[1:]))
    print(min([4, 1], *[]), max([4, 1], *[]), min("b", *[]))
    print(max(*[[1, 5], [2]], key=len), min(*["bb", "a"], key=len))
    print(max(3, 3.5, *xs), min(-1, *xs, 0))
    vals = {"a": 1, "b": 7}
    print(max(*vals.values()), max(vals["a"], *xs))
    for call in (0, 1):
        try:
            print(max(*[]) if call == 0 else min(*[]))
        except TypeError as e:
            print("TypeError", e)
    for call in (0, 1):
        try:
            print(max(*xs, default=0) if call == 0 else min(xs[0], *xs[1:], default=1))
        except TypeError as e:
            print("TypeError", e)
    print(max(*[[1, 5]], default=0), min([], default=-2), max([4, 2], *[]))


if __name__ == "__main__":
    main()
"""

CASES = [
    ('print_star_statement_typed', PRINT_STAR_STATEMENT),
    ('datetime_in_tuples_ordered_and_subtracted', DT_TUPLE_ORDER),
    ('user_lt_orders_instances_on_general_path', LT_DISPATCH),
    ('libm_helper_inside_key_lambda_on_general_path', INTRINSIC_LEAK),
    ('combinations_permutations_zip_longest_values', ITERTOOLS_LISTS),
    ('math_modf', MODF),
    ('textwrap_fsum_prod', TEXTWRAP_FSUM_PROD),
    ('boolop_value_is_an_operand', BOOLOP_VALUE),
    ('heapq_and_key_closure_on_general_path', DIJKSTRA_CLOSURE),
    ('bin_hex_oct_isspace_on_general_path', BASE_BUILTINS),
    ('lambda_calling_builtins', LAMBDA_BUILTINS),
    ('tuple_local_into_iterating_builtins', TUPLE_WHOLE),
    ('sorted_generator_of_dates', DATE_GENEXP),
    ('print_star_of_a_computed_list', PRINT_STAR),
    ('math_comb_perm_lcm', MATH_INT),
    ('comprehension_loop_variable_in_lambda', COMP_LAMBDA),
    ('takewhile_dropwhile_closure', WHILE_CLOSURE),
    ('bytes_hex_separator', HEX_SEP),
    ('bisect_module_bisect_on_general_path', BISECT_MODULE),
    ('starred_max_min_arguments', STAR_MAX),
]


def build_and_run(directory, text, name, ir):
    source, exe = Path(directory, name + '.ail'), Path(directory, name)
    source.write_text(text, encoding='utf-8')
    env = dict(os.environ, AIL_IR='1' if ir else '0')
    built = subprocess.run([sys.executable, '-B', str(ROOT / 'ail_chatgpt.py'), 'compile', source.name,
                            '--syntax', 'python', '-o', exe.name], cwd=directory,
                           capture_output=True, text=True, timeout=600, env=env)
    expected = subprocess.run([sys.executable, str(source)], capture_output=True, timeout=60)
    if built.returncode != 0:
        return built, None, expected
    return built, subprocess.run([str(exe)], capture_output=True, timeout=60), expected


class CorpusFindings3(unittest.TestCase):
    def check(self, slug, text, ir):
        with tempfile.TemporaryDirectory() as directory:
            built, ran, expected = build_and_run(directory, text, slug + ('_ir' if ir else ''), ir)
            self.assertEqual(expected.returncode, 0, expected.stderr)
            self.assertEqual(built.returncode, 0, built.stdout + built.stderr)
            self.assertEqual((ran.returncode, ran.stdout), (expected.returncode, expected.stdout), ran.stderr)

    def test_cases_default(self):
        for slug, text in CASES:
            with self.subTest(slug):
                self.check(slug, text, False)

    def test_cases_ir(self):
        for slug, text in CASES:
            with self.subTest(slug):
                self.check(slug, text, True)


if __name__ == '__main__':
    unittest.main()
