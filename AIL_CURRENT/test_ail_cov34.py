"""Cov34: nested generator expressions consumed in place, compared with CPython 3.12.

A generator expression is materialised like a list comprehension on the general path.  An inner
generator expression may take that same lowering only when the whole value is read at the point it is
built: each generator in the nesting is a lone positional argument of a whole-value builtin
(sum, list, sorted, join, ...) or a starred unpack, and no generator in the nesting sits in another
generator's iterable.  CPython pulls such an iterable lazily and interleaves it with the outer loop,
so an eager list would change side-effect order, run past break/short-circuit, and snapshot a source
the loop may mutate; those shapes stay named refusals.  Extra call arguments, receivers whose
appends are interleaved (`extend`/`update`), and saved outer generators are refused for the same
reason: CPython evaluates or consumes them at a different point, and its inner generators are lazy
where this path stores lists.
"""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent

SUMS = r"""def src(n: int):
    print("src", n)
    return range(n)


def main() -> None:
    xs: list[int] = []
    ys: list[int] = [3, -2]
    print(sum(sum(y for y in src(x)) for x in [1, 2]))
    print(sum(sum(y for y in src(x)) for x in xs))
    print(sum(sum(y for y in src(x)) for x in ys))
    print(" ".join(" ".join(str(v) for v in row) for row in [[], [1], [2, 3]]))
    print(list(list(z for z in range(y)) for y in [0, 1, 3]))
    print(sum(sum(y for y in [z]) for z in [1, 2, 3]))
    print(sum(x for x in [-1, 0, 2] if any(y for y in [x])))
    print(min(sum(y for y in range(x)) for x in [2, 4]))
    print(max(sum(y for y in range(x)) for x in [2, 4]))
    print(sorted(sum(y for y in range(x)) for x in [3, 1, 2]))
    for value in [sum(y for y in range(x)) for x in [0, 2]]:
        print("loop", value)


main()
"""

ROUTES = r"""class Holder:
    def __init__(self, rows: list[list[int]]) -> None:
        self.total = sum(sum(v for v in row) for row in rows)


def add_all(rows: list[list[int]]) -> int:
    return sum(sum(v for v in row) for row in rows if row)


def main() -> None:
    rows = [[1, 2], [3], [], [-4, 5]]
    print(add_all(rows))
    print(add_all([]))
    print(Holder(rows).total)
    print(Holder([]).total)
    d = {"total": sum(sum(v for v in row) for row in rows)}
    print(d["total"])
    parts = [sum(v for v in row) for row in rows]
    print(parts, parts[0], parts[-1])
    joined = "|".join(",".join(str(v) for v in row) for row in rows)
    print(joined)
    grid = [list(v * 2 for v in row) for row in rows]
    print(grid)
    nested = [sum(v for v in row) for row in grid]
    print(nested)


main()
"""

ALIASES = r"""def total(rows):
    return sum(sum(x for x in row) for row in rows)


def show(label: str, value: int) -> None:
    print(label, value)


class Box:
    def __init__(self, rows):
        self.value = total(rows)


def main() -> None:
    rows = [[1, 2], [3]]
    show("a", total(rows))
    show("b", total([]))
    values = [total(rows), total([]), sum(sum(x for x in row) for row in rows)]
    print(values)
    table = {"a": total(rows), "b": total([])}
    print(table)
    alias = rows
    print(total(alias))
    print(Box(rows).value)
    print([[sum(y for y in range(x)) for x in (0, 1)] for _ in (0,)])
    print(list(sum(y for y in range(x)) for x in ()))
    print(dict((key, sum(sum(x for x in row) for row in rows)) for key in ("k",)))


main()
"""

SAVED_NESTED = r"""def src(n):
    print("src", n)
    return range(n)


def main() -> None:
    g = ((y for y in src(x)) for x in [1, 2])
    print("made")
    print(next(next(g)))


main()
"""

ORDER = r"""sum_seen = []
join_seen = []
any_seen = []


def g(v):
    sum_seen.append(v)
    join_seen.append(v)
    any_seen.append(v)
    return v


def main() -> None:
    rows: list[list[int]] = [[1, 2], [3], [], [-4, 5]]
    print(sum(sum(g(v) for v in row) for row in rows))
    print(sum_seen)
    print("|".join(",".join(str(g(v)) for v in row) for row in rows))
    print(join_seen)
    print(list(x for x in [0, 1, 2] if any(g(y) for y in [x])))
    print(any_seen)


main()
"""

NESTED_ITERABLE = r"""log = []


def f(z):
    log.append("f%d" % z)
    return z


def g(y):
    log.append("g%d" % y)
    return y


def main() -> None:
    print(sum(g(y) for y in (f(z) for z in range(2))))
    print(log)


main()
"""

NESTED_BREAK = r"""log = []


def f(z):
    log.append(z)
    return z


def main() -> None:
    for y in (y for y in (f(z) for z in range(5))):
        log.append("body")
        break
    print(log)


main()
"""

NESTED_MUTATE = r"""xs = [1, 2]
seen = []


def main() -> None:
    for y in (y for y in (x for x in xs)):
        seen.append(y)
        if y == 1:
            xs.append(3)
    print(seen)


main()
"""

NESTED_START = r"""log = []


def f(x):
    log.append(x)
    return x


def start():
    log.append("start")
    return 0


def main() -> None:
    rows: list[list[int]] = [[1, 2]]
    print(sum((sum(f(x) for x in row) for row in rows), start()))
    print(log)


main()
"""

NESTED_INNER_START = r"""log = []


def f(x):
    log.append(x)
    return x


def start():
    log.append("start")
    return 0


def main() -> None:
    rows: list[list[int]] = [[1, 2]]
    print(sum(sum((f(x) for x in row), start()) for row in rows))
    print(log)


main()
"""

NESTED_EXTEND = r"""lst: list[int] = []


def g(v):
    lst.append(v)
    return v


def main() -> None:
    rows: list[list[int]] = [[1, 2], [3]]
    lst.extend(sum(g(v) for v in row) + len(lst) for row in rows)
    print(lst)


main()
"""

CASES = [
    ("sums", SUMS),
    ("routes", ROUTES),
    ("aliases", ALIASES),
    ("order", ORDER),
]


def build(directory, text, name, **env):
    source, exe = Path(directory, name + ".ail"), Path(directory, name)
    source.write_text(text, encoding="utf-8")
    built = subprocess.run([sys.executable, "-B", str(ROOT / "ail_chatgpt.py"), "compile", source.name,
                            "--syntax", "python", "-o", exe.name], cwd=directory, capture_output=True,
                           text=True, timeout=1800,
                           env=dict(os.environ, AIL_NO_CACHE="1", AIL_QUIET_FALLBACK="1", **env))
    return built, exe


class Programs(unittest.TestCase):
    def check(self, name, **env):
        text = dict(CASES)[name]
        with tempfile.TemporaryDirectory() as directory:
            oracle = Path(directory, "oracle.py")
            oracle.write_text(text, encoding="utf-8")
            want = subprocess.run([sys.executable, "-X", "utf8", str(oracle)], capture_output=True, timeout=300)
            built, exe = build(directory, text, "p_" + name, **env)
            self.assertEqual(built.returncode, 0,
                             "%s: %s%s" % (name, built.stdout[-400:], built.stderr[-600:]))
            got = subprocess.run([str(exe)], capture_output=True, timeout=300)
            self.assertEqual(got.returncode, want.returncode, "%s: %s" % (name, got.stderr[-300:]))
            self.assertEqual(got.stdout.decode(), want.stdout.decode(), name)

    def test_general_path(self):
        for name, _ in CASES:
            with self.subTest(program=name):
                self.check(name, AIL_UNIFIED_FORCE="1")

    def test_default_build(self):
        for name, _ in CASES:
            with self.subTest(program=name):
                self.check(name)


class Refused(unittest.TestCase):
    def refused(self, text, word, **env):
        with tempfile.TemporaryDirectory() as directory:
            built, _ = build(directory, text, "r", **env)
            self.assertNotEqual(built.returncode, 0)
            self.assertIn(word, built.stdout + built.stderr)

    def test_saved_nested_generator(self):
        self.refused(SAVED_NESTED, "nested inside another generator expression",
                     AIL_UNIFIED_FORCE="1")

    def test_saved_nested_generator_default(self):
        self.refused(SAVED_NESTED, "nested inside another generator expression")

    def test_nested_in_iterable(self):
        self.refused(NESTED_ITERABLE, "nested inside another generator expression",
                     AIL_UNIFIED_FORCE="1")

    def test_nested_in_iterable_default(self):
        self.refused(NESTED_ITERABLE, "nested inside another generator expression")

    def test_break_outside_inner(self):
        self.refused(NESTED_BREAK, "nested inside another generator expression",
                     AIL_UNIFIED_FORCE="1")

    def test_break_outside_inner_default(self):
        self.refused(NESTED_BREAK, "nested inside another generator expression")

    def test_mutation_during_iteration(self):
        self.refused(NESTED_MUTATE, "nested inside another generator expression",
                     AIL_UNIFIED_FORCE="1")

    def test_mutation_during_iteration_default(self):
        self.refused(NESTED_MUTATE, "nested inside another generator expression")

    def test_outer_extra_argument(self):
        self.refused(NESTED_START, "nested inside another generator expression",
                     AIL_UNIFIED_FORCE="1")

    def test_outer_extra_argument_default(self):
        self.refused(NESTED_START, "nested inside another generator expression")

    def test_inner_extra_argument(self):
        self.refused(NESTED_INNER_START, "nested inside another generator expression",
                     AIL_UNIFIED_FORCE="1")

    def test_inner_extra_argument_default(self):
        self.refused(NESTED_INNER_START, "nested inside another generator expression")

    def test_mutating_method_receiver(self):
        self.refused(NESTED_EXTEND, "nested inside another generator expression",
                     AIL_UNIFIED_FORCE="1")

    def test_mutating_method_receiver_default(self):
        self.refused(NESTED_EXTEND, "nested inside another generator expression")


if __name__ == "__main__":
    unittest.main()
