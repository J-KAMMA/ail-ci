"""Cov34: nested generator expressions consumed in place, compared with CPython 3.12.

A generator expression is materialised like a list comprehension on the general path.  An inner
generator expression may take that same lowering when every generator expression in the nesting is
read at the point it is built: the outer one is an argument of a whole-value builtin (sum, join,
list, sorted, ...), a for/comprehension source, or a starred/unpacked value, and each inner one is
consumed the same way.  Then the value is created and read at the same point as CPython.  A saved
outer generator still names the refusal: CPython creates its inner generators lazily, so the eager
inner lowering would move their side effects and store lists where CPython stores generators.
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
    print(sum(y for y in (z for z in [1, 2, 3])))
    print(sum(x for x in [-1, 0, 2] if any(y for y in [x])))
    print(min(sum(y for y in range(x)) for x in [2, 4]))
    print(max(sum(y for y in range(x)) for x in [2, 4]))
    print(sorted(sum(y for y in range(x)) for x in [3, 1, 2]))
    for value in (sum(y for y in range(x)) for x in [0, 2]):
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

CASES = [
    ("sums", SUMS),
    ("routes", ROUTES),
    ("aliases", ALIASES),
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


if __name__ == "__main__":
    unittest.main()
