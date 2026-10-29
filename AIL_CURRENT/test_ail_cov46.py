"""cov46: a generator expression nested inside another is built when its inner generator is
consumed by a call that reads every element (sum, join, list, sorted, max, extend, ...).

The general path materialises generator expressions, so a nested one used as a saved,
short-circuited or `for`-loop value would run (and could raise from) elements CPython never
reaches; that stays a named compile-time refusal.  A nested generator is built when both it and
the generator around it are read to the end right where they are written: the sole argument of a
fully consuming call (sum, join, list, sorted, max, extend, ...), or a comprehension source.  It
is then evaluated at the same point in both implementations, on the forced general path and on
the default build that falls back to it.
"""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent

PROGRAMS = {}
PROGRAMS['nested_join'] = r'''def main():
    rows = [[1, 2, 3], [], [-4, 5], [0]]
    print("\n".join(" ".join(str(v) for v in row) for row in rows))
    print("|".join(" ".join(f"{v:>3}" for v in row) for row in rows if row))
    print("[" + "\n".join(" ".join(str(v * 2) for v in row) for row in rows) + "]")


main()
'''
PROGRAMS['nested_sum'] = r'''def main():
    rows = [[1, 2, 3], [], [-4, 5], [0]]
    print(sum(sum(v for v in row) for row in rows))
    print(sum(sum(v * v for v in row) for row in rows if row))
    print(max(sum(v for v in row) for row in rows))
    print(sorted(sum(v for v in row) for row in rows))
    print(list(sum(v for v in row) for row in rows))


main()
'''
PROGRAMS['nested_fstring'] = r'''def main():
    quarters = ("q1", "q2")
    data = {"a": {"q1": 1, "q2": -2}, "b": {"q1": 5, "q2": 6}}
    print("".join(f"{sum(data[r][q] for r in data):>5}" for q in quarters))
    total = sum(sum(data[r][q] for q in quarters) for r in data)
    print(total)


main()
'''
PROGRAMS['nested_routes'] = r'''class Box:
    def __init__(self, rows):
        self.rows = rows


def show(rows):
    return "/".join(",".join(str(x) for x in row) for row in rows)


def main():
    b = Box([[1, 2], [3]])
    d = {"rows": [[4], [5, 6, 7]]}
    print(show([[8, 9]]))
    print(show(b.rows))
    print(show(d["rows"]))
    print(show([[-1, 0], []]))
    print(sum(sum(x for x in row) for row in b.rows), sum(sum(x for x in row) for row in d["rows"]))


main()
'''
PROGRAMS['nested_methods'] = r'''def main():
    rows = [[1, 2], [3, 4], [5]]
    out = []
    out.extend(sum(x for x in row) for row in rows)
    print(out)
    parts = []
    parts.extend(",".join(str(x) for x in row) for row in rows)
    print(parts)
    d = {}
    d.update((str(i), sum(x for x in row)) for i, row in enumerate(rows))
    print(d)


main()
'''
PROGRAMS['nested_depth'] = r'''def main():
    deep = [[[1, 2], [3]], [[4]]]
    print(sum(sum(sum(z for z in y) for y in x) for x in deep))
    print(";".join(" ".join(str(sum(z for z in y)) for y in x) for x in deep))


main()
'''
PROGRAMS['nested_empty'] = r'''def main():
    rows = []
    print("[" + "|".join(" ".join(str(v) for v in row) for row in rows) + "]")
    print(sum(sum(v for v in row) for row in rows))
    one = [[-1]]
    print(sum(sum(v for v in row) for row in one))


main()
'''
PROGRAMS['nested_containers'] = r'''def main():
    rows = [[1, 2], [], [3]]
    print(list(sum(v for v in row) for row in rows))
    print(tuple("".join(str(v) for v in row) for row in rows))
    print(sorted(set(len([v for v in row]) for row in rows)))
    print(sorted(frozenset("".join(str(v) for v in row) for row in rows)))
    print(dict((str(i), "".join(str(v) for v in row)) for i, row in enumerate(rows)))
    print(bytes(sum(v for v in row) for row in rows))
    print(bytearray(sum(v for v in row) for row in rows))


main()
'''
PROGRAMS['nested_comp_source'] = r'''def main():
    rows = [[1, 2], [], [3]]
    print([s for s in (" ".join(str(v) for v in row) for row in rows)])
    print(sorted([len(s) for s in (",".join(str(v) for v in row) for row in rows)]))


main()
'''


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


SHORT_CIRCUIT = r'''def f(x):
    print("eval", x)
    return x


def main():
    print(any(f(y) for y in (f(x) for x in [1, 2, 3])))


main()
'''
SAVED = r'''def f(v):
    print("eval", v)
    return v


def main():
    rows = [[1, 2], [3]]
    g = (" ".join(str(f(v)) for v in row) for row in rows)
    print("made")
    print(list(g))


main()
'''

FOR_BREAK = r'''def f(v):
    print("eval", v)
    return v


def main():
    rows = [[1, 2], [3]]
    for s in (" ".join(str(f(v)) for v in row) for row in rows):
        print(s)
        break


main()
'''


class Refused(unittest.TestCase):
    def refused(self, name, text):
        with tempfile.TemporaryDirectory() as directory:
            for env in ({"AIL_UNIFIED_FORCE": "1"}, {}):
                with self.subTest(program=name, env=env):
                    built, _ = build(directory, text, "r", **env)
                    self.assertEqual(built.returncode, 3, built.stdout + built.stderr)
                    self.assertIn("not in the subset", built.stdout + built.stderr)

    def test_nested_generator_in_short_circuit_call(self):
        self.refused("short_circuit", SHORT_CIRCUIT)

    def test_nested_generator_saved_or_for_loop(self):
        self.refused("saved", SAVED)
        self.refused("for_break", FOR_BREAK)


if __name__ == "__main__":
    unittest.main()
