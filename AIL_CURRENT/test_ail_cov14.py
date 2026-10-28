"""Branch cov14: a generator expression nested inside another one, when the inner one is read
completely by an eager consumer (`sum`, `min`, `max`, `any`, `all`, `list`, `tuple`, `sorted`,
`str.join`, ...), compared with CPython 3.12 on both builds.

The corpus programs that were refused for this use the inner generator as the argument of `sum`
or `str.join` inside the outer element; materialising it at the same point is exact.  Any other
nesting (the inner generator is the outer one's iterable, so the outer can stop early), a user
method/function that merely has a consuming name, and a call with `key=` or another argument keep
the named compile-time refusal.
"""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent

PROGRAMS = {}
PROGRAMS['nested_sum'] = r'''rows = [[1, 2, 3], [4, 5], [], [-2, -7]]
print([sum(v * 2 for v in row) for row in rows])
print([f"{sum(v * 2 for v in row):>6}" for row in rows])
def show(rs):
    for row in rs:
        print(f"{sum(v + 1 for v in row):>4}|{sum(v / 2 for v in row):.2f}")
show(rows)
print(sum(sum(v for v in row) for row in rows))
'''
PROGRAMS['nested_join'] = r'''rows = [["a", "bb"], ["", "ccc"], []]
print([" ".join(str(v) for v in row) for row in rows])
print([f"{' '.join(str(v) for v in row):>8}!" for row in rows])
def emit(rs):
    for row in rs:
        print("[" + ",".join(f"{' '.join(str(v) for v in row)}" for v in [0]) + "]")
emit(rows)
print("|".join(str(v) for v in ["x", "y"]))
print("|".join(str("|").join(str(v) for v in row) for row in rows))
sep = " "
print("|".join(f"{sep}".join(str(v) for v in row) for row in rows))
'''
PROGRAMS['nested_routes'] = r'''class Box:
    def __init__(self, rows):
        self.rows = rows
    def dump(self):
        return [sum(v * v for v in row) for row in self.rows]

d = {"rows": [[1, 2], [3]]}
def calc(rs):
    return [sum(v - 1 for v in row) for row in rs]
print(calc(d["rows"]))
print(calc([[10, 20]]))
b = Box([[2, 3], []])
print(b.dump())
print([sum(v for v in row) for row in b.rows])
items = [Box([[5]]), Box([[6, 7]])]
print([sum(v for v in it.rows[0][:1]) for it in items])
print([sum(sum(v for v in row) for row in it.rows) for it in items])
print([sum(min(v for v in row) for row in d["rows"])])
print([max(sum(v for v in row) for row in d["rows"])])
print(any(sum(v for v in row) > 3 for row in d["rows"]))
print(all(sum(v for v in row) > 0 for row in d["rows"]))
print(list(sum(v for v in row) for row in d["rows"]))
print(tuple(sum(v for v in row) for row in d["rows"]))
print(sorted(sum(v for v in row) for row in d["rows"]))
'''
PROGRAMS['nested_any'] = r'''rows = [[1], [0, 2], []]
print(sum(any(v for v in row) for row in rows))
print(list(any(v for v in row) for row in rows))
print(list(all(v for v in row) for row in rows))
print(sum(any(v > 1 for v in row) for row in rows))
'''
PROGRAMS['nested_empty'] = r'''empty = []
print([sum(v for v in row) for row in empty])
print([sum(v for v in row) for row in [[]]])
print([sum(v for v in row) for row in [[-1], [0], [1, -2]]])
print([min(v for v in row) if row else -99 for row in [[3, 1], [], [-4]]])
print([max(v for v in row) if row else -99 for row in [[3, 1], [], [-4]]])
print([any(v for v in row) for row in [[], [0], [0, 2]]])
print([all(v for v in row) for row in [[], [0], [2, 3]]])
b = [[True, False], [True]]
print([sum(v for v in row) for row in b])
'''


def build(directory, text, name, **env):
    source, exe = Path(directory, name + ".ail"), Path(directory, name)
    source.write_text(text, encoding="utf-8")
    built = subprocess.run([sys.executable, "-B", str(ROOT / "ail_chatgpt.py"), "compile",
                            source.name, "--syntax", "python", "-o", exe.name],
                           cwd=directory, capture_output=True, text=True, timeout=1800,
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
            self.assertEqual(got.returncode, want.returncode,
                             "%s: %s" % (name, got.stderr[-300:]))
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
    REFUSALS = {}
    REFUSALS['nested_lazy'] = r'''values = (x for x in (y for y in range(5)))
for v in values:
    print(v)
    break
'''
    REFUSALS['custom_extend'] = r'''log = []
def f(x):
    log.append(x)
    return x
class C:
    def extend(self, it):
        v = next(iter(it))
        return (v, len(log))
c = C()
print(list(c.extend(f(x) for x in [1, 2, 3]) for _ in [0]))
'''
    REFUSALS['custom_update'] = r'''log = []
def f(x):
    log.append(x)
    return x
class C:
    def update(self, it):
        return next(iter(it))
c = C()
print(list(c.update(f(x) for x in [1, 2, 3]) for _ in [0]))
print(log)
'''
    REFUSALS['custom_join'] = r'''log = []
def f(x):
    log.append(x)
    return x
class C:
    def join(self, it):
        return next(iter(it))
c = C()
print(list(c.join(f(x) for x in [1, 2, 3]) for _ in [0]))
print(log)
'''
    REFUSALS['max_key'] = r'''log = []
def f(x):
    log.append(("f", x))
    return x
def k(x):
    log.append(("k", x))
    return -x
print(list(max((f(x) for x in [1, 2, 3]), key=k) for _ in [0]))
print(log)
'''
    REFUSALS['shadowed_sum'] = r'''def sum(it):
    return next(iter(it))
log = []
def f(x):
    log.append(x)
    return x
print(list(sum(f(x) for x in [1, 2, 3]) for _ in [0]))
print(log)
'''
    REFUSALS['sum_start'] = r'''log = []
def f(x):
    log.append(x)
    return x
print(list(sum((f(x) for x in [1, 2, 3]), 10) for _ in [0]))
print(log)
'''

    def refused(self, text, **env):
        with tempfile.TemporaryDirectory() as directory:
            built, _ = build(directory, text, "r", **env)
            self.assertNotEqual(built.returncode, 0)
            self.assertIn("a generator expression nested inside another generator expression",
                          built.stdout + built.stderr)

    def test_refusal_general_path(self):
        for name, text in self.REFUSALS.items():
            with self.subTest(program=name):
                self.refused(text, AIL_UNIFIED_FORCE="1")

    def test_refusal_default_build(self):
        for name, text in self.REFUSALS.items():
            with self.subTest(program=name):
                self.refused(text)


if __name__ == "__main__":
    unittest.main()
