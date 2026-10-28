"""Coverage 16: a generator expression nested inside another one, when the inner generator is
consumed at once (sum/join/list/tuple/dict/sorted/min/max, a starred call or unpacking).

CPython creates the inner generator object lazily; the general path materialises it eagerly.  That
is the same point in the program only where the consumer reads every element without an early
exit.  Such a site now builds on both builds and must print what CPython prints.  A nested inner
generator that is saved as a value, fed to next()/any()/all(), used as a for iterable, or used
inside a try body stays a named compile-time refusal.
"""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent

PROGRAMS = {}
PROGRAMS['join_routes'] = r'''class C:
    def __init__(self):
        self.rows = [[1, 2], [3]]


def render(rows):
    return "\n".join(" ".join(str(v) for v in row) for row in rows)


c = C()
d = {"k": [[4, 5], [6]], "empty": []}
print(render([[7, 8], [9]]))
print(render(c.rows))
print(render(d["k"]))
print(render([c.rows[0], d["k"][1]]))
print(render(d["empty"]))
print(render([[], [10]]))
'''
PROGRAMS['sum_types'] = r'''def total(rows):
    return sum(sum(x for x in row) for row in rows)


def hi(rows):
    return [max(x for x in row) for row in rows if row]


rows = [[], [1, -2], [3.5, 4], [True, False]]
print(total(rows))
print(hi(rows))
print(total([]))
print(sum(min(x for x in row) for row in [[-5], [0], [7]]))
print(sum(sum(x for x in row) for row in [[1.5], [-0.5], [2.0]]))
'''
PROGRAMS['builtins'] = r'''rows = [[3, 1, 2], [], [-5, 0]]
print(sorted(sorted(x for x in row) for row in rows))
print(list(list(x for x in row) for row in rows))
print(tuple(tuple(x for x in row) for row in rows))
print(dict((k, sum(x for x in row)) for k, row in [("a", [1, 2]), ("b", [])]))
print(sum(len(list(x for x in row)) for row in rows))
'''
PROGRAMS['methods_star'] = r'''def f(*args):
    return len(args), sum(args)


rows = [[1, 2], [], [3, 4, 5]]
out = []
out.extend(list(x for x in row) for row in rows)
print(out)
print(list(f(*(x for x in row)) for row in rows))
print("\n".join(",".join(str(x) for x in row) for row in rows))
print(sum(f(*(x for x in row))[1] for row in rows))
'''
PROGRAMS['exception'] = r'''def wrap(rows):
    return sum(sum(10 // x for x in row) for row in rows)


print(wrap([[1, 2], [3, 5]]))
try:
    print(wrap([[1, 2], [3, 0, 5]]))
except ZeroDivisionError as e:
    print("caught", e)
'''
PROGRAMS['float_bool'] = r'''rows = [[1.5, -2.0], [0.0], [True, False]]
print(sum(sum(x for x in row) for row in rows))
print(max(max(x for x in row) for row in rows))
print(min(min(x for x in row) for row in rows))
print([sum(x for x in row) for row in rows])
print(list(sum(x for x in row) for row in rows))
'''

REFUSALS = {
    'saved_inner': (r'''g = ((x * x for x in row) for row in [[1, 2], [3]])
for inner in g:
    print(list(inner))
''', 'nested inside another generator expression'),
    'next_inner': (r'''print(list(next(x for x in row) for row in [[1, 2], [3]]))
''', 'nested inside another generator expression'),
    'any_inner': (r'''print(list(any(x > 1 for x in row) for row in [[1, 2], [3]]))
''', 'nested inside another generator expression'),
    'for_inner': (r'''print(sum(sum(y for y in (x for x in row)) for row in [[1, 2], [3]]))
''', 'nested inside another generator expression'),
    'try_inner': (r'''def wrap(rows):
    try:
        return sum(sum(x for x in row) for row in rows)
    except ValueError as e:
        return -1
print(wrap([[1, 2], [3, 5]]))
print(wrap([]))
''', 'nested inside another generator expression'),
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
    def refused(self, text, word):
        with tempfile.TemporaryDirectory() as directory:
            built, _ = build(directory, text, "r", AIL_UNIFIED_FORCE="1")
            self.assertNotEqual(built.returncode, 0)
            self.assertIn(word, built.stdout + built.stderr)

    def test_nested_forms(self):
        for name, (text, word) in REFUSALS.items():
            with self.subTest(case=name):
                self.refused(text, word)


if __name__ == "__main__":
    unittest.main()
