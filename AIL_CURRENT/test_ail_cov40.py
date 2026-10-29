"""Branch cov40: a generator expression nested inside another one is built when every nested
generator is fully consumed at the point the enclosing one is built, and stays refused by name
otherwise.  Compared with CPython 3.12 on the general path (AIL_UNIFIED_FORCE=1) and on the
default build, which falls back to it.

The general path materialises a generator expression as a list.  A nested generator whose whole
content is read by a call at the same point (`sum(...)`, `max(...)`, `join(...)`, ...), a starred
unpack, or a tuple/list unpacking assignment is therefore observationally lazy; one used as a
for/comprehension iterable, as an element value, by `next()`/`any()`/`all()`, or passed to an
unknown call still runs its body too early, so it is refused by name.
"""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent

PROGRAMS = {}
PROGRAMS['join'] = r'''def show(rows: list[list[int]]) -> str:
    return "\n".join(" ".join(str(v) for v in row) for row in rows)


def wrap(rows: list[list[int]]) -> str:
    return "[" + show(rows) + "]"


class Box:
    def __init__(self, rows: list[list[int]]) -> None:
        self.rows = rows


def main() -> None:
    rows = [[1, -2], [], [3]]
    print(show(rows))
    print(wrap(rows))
    b = Box(rows)
    print(show(b.rows))
    data = {"r": rows}
    print(show(data["r"]))
    print(show([rows[0], rows[2]]))
    print(show([]))
    print("\n".join(" ".join(str(x) for x in row) for row in rows))


main()
'''
PROGRAMS['sums'] = r'''def totals(groups: dict[str, list[int]]) -> str:
    keys = sorted(groups)
    return "".join(f"{k}:{sum(v for v in groups[k]):>4}" for k in keys)


def inner(i: int) -> int:
    print("inner", i)
    return i


def main() -> None:
    print(totals({"a": [1, 2, 3], "b": [], "c": [-4, 5]}))
    print(totals({}))
    print(list(sum(inner(i) for i in range(x)) for x in range(3)))
    print("|".join(str(sum(inner(i) for i in range(x))) for x in range(2)))
    print(tuple(sum(inner(i) for i in range(x)) for x in [2, 0, 1]))
    print(sorted(sum(inner(i) for i in range(x)) for x in [2, 2, 0]))
    print(max(sum(inner(i) for i in range(x)) for x in range(3)))
    print(min(sum(inner(i) for i in range(x)) for x in range(1, 4)))


main()
'''
PROGRAMS['routes'] = r'''class Holder:
    def __init__(self, rows: list[list[int]]) -> None:
        self.rows = rows


def render(rows: list[list[int]]) -> str:
    return "\n".join(" ".join(str(x) for x in row) for row in rows)


def take(rows: list[list[int]]) -> str:
    return render(rows)


def main() -> None:
    rows = [[1, 2], [3]]
    print(render(rows))
    print(render(Holder(rows).rows))
    lst = [rows, []]
    print(render(lst[0]))
    d = {"k": rows}
    print(render(d["k"]))
    print(take(rows))


main()
'''
REFUSED = {
    'iterable': 'print(list(x for x in (y for y in range(3))))\n',
    'element': 'print(list((x for x in [i]) for i in range(3)))\n',
    'next': 'print(list(next(x for x in [i]) for i in range(3)))\n',
}


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
            want = subprocess.run([sys.executable, "-X", "utf8", str(oracle)], capture_output=True, timeout=300)
            built, exe = build(directory, text, "p_" + name, **env)
            self.assertEqual(built.returncode, 0, "%s: %s%s" % (name, built.stdout[-400:], built.stderr[-600:]))
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
    def refused(self, text, **env):
        with tempfile.TemporaryDirectory() as directory:
            built, _ = build(directory, text, "r", **env)
            self.assertNotEqual(built.returncode, 0, built.stdout[-800:])
            self.assertIn("nested inside another generator expression", built.stdout + built.stderr)

    def test_unsafe_nested_by_name(self):
        for name, text in REFUSED.items():
            with self.subTest(shape=name):
                self.refused(text, AIL_UNIFIED_FORCE="1")

    def test_unsafe_nested_default(self):
        for name, text in REFUSED.items():
            with self.subTest(shape=name):
                self.refused(text)


if __name__ == "__main__":
    unittest.main()
