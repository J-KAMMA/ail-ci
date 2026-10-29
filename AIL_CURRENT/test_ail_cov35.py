"""Branch cov35: a generator expression nested inside another generator expression on the general
path, when every nested one is read to exhaustion there (join/sum/list/sorted/min/max, a
comprehension source, a starred call or a tuple unpacking assignment), each compared with CPython
3.12.

* PROGRAMS are compiled twice (AIL_UNIFIED_FORCE=1, the general path; and the default build, which
  falls back to it) and must print what CPython prints.  They cover empty and negative inputs,
  bool/float/large int values, aliasing, a three-level nest, an inner generator as the outer
  iterable, and values arriving through an argument, a list item, an attribute and a dict value.
* a nested generator saved as a value, consumed by `next`, or used with any()/all() is not
  materialised safely, so it stays a named compile-time refusal.
"""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent

PROGRAMS = {}
PROGRAMS['join'] = r'''def render(rows, label):
    return label + ":" + "\n".join(" ".join(str(v) for v in row) for row in rows)

class Holder:
    def __init__(self, rows):
        self.rows = rows

rows = [[1, -2, 3], [4], [], [0, 0]]
h = Holder([[-1], [10, 20]])
d = {"rows": [[7, 8], [9]]}
print(render(rows, "arg"))
print(render(h.rows, "attr"))
print(render(d["rows"], "dict"))
print(render([rows[0], rows[1]], "item"))
print(render([], "empty"))
print("\n".join(" ".join(str(v) for v in r) for r in rows))
'''
PROGRAMS['sum'] = r'''def total(grid, scale):
    return sum(sum(v * scale for v in row) for row in grid)

grid = [[1, -2, 3], [4], [], [5, 6]]
print(total(grid, 1))
print(total(grid, -2))
print(sum(sum(v for v in row) for row in []))
print(min(min(v for v in row) for row in [[3, 1], [2, -4]]))
print(max(max(v for v in row) for row in [[3, 1], [2, -4]]))
print(list(sum(v for v in row) for row in grid))
print(sorted((sum(v for v in row) for row in grid), reverse=True))
print(dict((r, sum(v for v in row)) for r, row in enumerate(grid)))
'''
PROGRAMS['bounds'] = r'''def f(xs):
    return list(sum(x + n for x in range(n)) for n in (xs))

def nested(rows):
    return list(sum(v + 0.5 for v in row) for row in (r for r in rows))

class Box:
    def __init__(self):
        self.data = {"rows": [[1.5, -2.0], [3.0]]}

print(f([0, 1, 2, -3]))
print(f([]))
print(nested([[1, 2], [3]]))
print(nested([]))
print("\n".join("|".join(str(a * b) for b in range(3)) for a in (-2, 0, 4)))
vals = (str(x) for x in [True, False, -1, 0, 2 ** 40])
print(" ".join("".join(c for c in s) for s in vals))
a = [1, 2]
b = [a, a]
print([sum(x for x in row) for row in b])
print(sum(sum(x for x in row) for row in b))
print(list(sum(v for v in row) for row in (" ".join(str(v) for v in r) for r in [[1, 2], [3]])))
box = Box()
print(list(sum(v for v in row) for row in box.data["rows"]))
print(set(sum(v for v in row) for row in [[1, 2], [3], [1, 2]]))
'''

REFUSED = (
    ("saved", "g = (x for x in (y for y in [1, 2, 3]))\nprint(list(g))\n",
     "nested inside another generator expression"),
    ("next", "print(next(x for x in (y for y in [1, 2, 3])))\n",
     "nested inside another generator expression"),
    ("any", "print(any(x > 1 for x in (y for y in [0, 1, 2])))\n",
     "generator expression whose iterable is itself"),
)


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
        text = PROGRAMS[name]
        with tempfile.TemporaryDirectory() as directory:
            oracle = Path(directory, "oracle.py")
            oracle.write_text(text, encoding="utf-8")
            want = subprocess.run([sys.executable, "-X", "utf8", str(oracle)],
                                  capture_output=True, timeout=300)
            built, exe = build(directory, text, "p_" + name, **env)
            self.assertEqual(built.returncode, 0,
                             "%s: %s%s" % (name, built.stdout[-400:], built.stderr[-600:]))
            got = subprocess.run([str(exe)], capture_output=True, timeout=300)
            self.assertEqual(got.returncode, want.returncode, "%s: %s" % (name, got.stderr[-300:]))
            self.assertEqual(got.stdout.decode(), want.stdout.decode(), name)

    def test_general_path(self):
        for name in PROGRAMS:
            with self.subTest(program=name):
                self.check(name, AIL_UNIFIED_FORCE="1")

    def test_default_build(self):
        for name in PROGRAMS:
            with self.subTest(program=name):
                self.check(name)


class Refused(unittest.TestCase):
    def refused(self, text, word, **env):
        with tempfile.TemporaryDirectory() as directory:
            built, _ = build(directory, text, "r", **env)
            self.assertNotEqual(built.returncode, 0)
            self.assertIn(word, built.stdout + built.stderr)

    def test_nested_generator_saved_as_value(self):
        self.refused(REFUSED[0][1], REFUSED[0][2], AIL_UNIFIED_FORCE="1")
        self.refused(REFUSED[0][1], REFUSED[0][2])

    def test_nested_generator_under_next(self):
        self.refused(REFUSED[1][1], REFUSED[1][2], AIL_UNIFIED_FORCE="1")

    def test_nested_generator_under_any(self):
        self.refused(REFUSED[2][1], REFUSED[2][2], AIL_UNIFIED_FORCE="1")


if __name__ == "__main__":
    unittest.main()
