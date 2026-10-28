"""Branch cov21: a generator expression nested inside another generator expression, when the
inner one is read to exhaustion at the point it is created (the sole argument of
sum/min/max/list/tuple/sorted, a comprehension source, a starred unpack, or `.join` on a string
literal).

The general path used to refuse every nested generator expression because it materialises
generators eagerly.  For an outer and inner generator that those consumers read completely
before returning, materialising them there is observationally the same as CPython's lazy
generator.

* PROGRAMS are compiled with AIL_UNIFIED_FORCE=1 (the general path) and on the default build,
  and must print what CPython 3.12 prints;
* contexts that do not exhaust the generator at creation stay refused by name: a `for` loop
  (which can break), a tuple/list unpack target (which pulls len(target)+1 elements), a
  generator saved as a value, a consumer with another argument or keyword (evaluated before
  the generator in CPython), and an incrementally validating consumer such as `dict`.
"""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent
PKG = ROOT / "python" / "pkg-v12"
if str(PKG) not in sys.path:
    sys.path.insert(0, str(PKG))

PROGRAMS = {}
PROGRAMS['sums'] = r'''rows = [[1, 2, 3], [4, 5], [], [-2, 7]]
print(sum(sum(v for v in row) for row in rows))
print([sum(v for v in row) for row in rows])
print(min(sum(v for v in row) for row in rows), max(sum(v for v in row) for row in rows))
print(sorted(sum(v for v in row) for row in rows))
print(sum(sum(v for v in row) for row in [[], [], []]))
print(sum(sum(v for v in row) for row in [[0], [0, 0]]))
'''
PROGRAMS['joins'] = r'''rows = [["a", "b"], ["c"], [], ["d", "e", "f"]]
print("|".join(" ".join(x for x in row) for row in rows))
print("|".join(f"{sum(len(x) for x in row):>3}" for row in rows))
print("".join("[" + ",".join(str(v) for v in row) + "]" for row in [[1, 2], [3]]))
print("|".join("%d" % sum(v for v in row) for row in [[10], [20, 30]]))
'''
PROGRAMS['types'] = r'''ints = [[10 ** 30, -(10 ** 30)], [2 ** 70], [-5]]
floats = [[1.5, 2.25], [0.1], [-0.5]]
bools = [[True, False], [True, True]]
print(sum(sum(v for v in row) for row in ints))
print(sum(sum(v for v in row) for row in floats))
print(sum(sum(1 for v in row if v) for row in bools))
print("|".join("%.2f" % sum(v for v in row) for row in floats))
print(sum(sum(v for v in row) for row in [[True, 2], [False]]))
'''
PROGRAMS['sources'] = r'''def total(rows):
    return sum(sum(v for v in row) for row in rows)

data = {"g": [[4, 5], [6]]}
class Holder:
    def __init__(self):
        self.rows = [[7], [8, 9]]
h = Holder()
allrows = [[[1], [2]], [[3, 4]]]
print(total([[1, 2], [3]]))
print(sum(sum(v for v in row) for row in data["g"]))
print(sum(sum(v for v in row) for row in h.rows))
print(sum(sum(v for v in row) for row in allrows[0]))
a = [[1, 2], [3]]
b = a
b.append([4, 5])
print(sum(sum(v for v in row) for row in a))
'''
PROGRAMS['flat'] = r'''rows = [[1, 2], [3, 4]]
print([sum(y for y in (x * 2 for x in row)) for row in rows])
print([sum(row[i] for i in range(len(row))) for row in rows])
print(sum(x * y for row in rows for x in row for y in row if y > x))
print(list(sum(v for v in row) for row in rows))
'''


def build(directory, text, name, **env):
    source, exe = Path(directory, name + ".ail"), Path(directory, name)
    source.write_text(text, encoding="utf-8")
    built = subprocess.run([sys.executable, "-B", str(ROOT / "ail_chatgpt.py"), "compile", source.name, "--syntax", "python",
                            "-o", exe.name], cwd=directory, capture_output=True, text=True, timeout=1800,
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
    def refused(self, text, word, **env):
        with tempfile.TemporaryDirectory() as directory:
            built, _ = build(directory, text, "r", **env)
            self.assertNotEqual(built.returncode, 0)
            self.assertIn(word, built.stdout + built.stderr)

    def both(self, text):
        word = "nested inside another generator expression"
        self.refused(text, word, AIL_UNIFIED_FORCE="1")
        self.refused(text, word)

    def test_saved_inner_generator(self):
        self.both("rows = [[1, 2], [3]]\ng = ((y for y in row) for row in rows)\nprint(list(list(x) for x in g))\n")

    def test_for_break_is_not_exhaustion(self):
        self.both("rows = [[1], [2], [3]]\n"
                  "def bad(x):\n"
                  "    if x == 3:\n"
                  "        raise RuntimeError('boom')\n"
                  "    return x\n"
                  "for r in (sum(bad(v) for v in row) for row in rows):\n"
                  "    print(r)\n"
                  "    break\n"
                  "print('done')\n")

    def test_sibling_arguments_are_evaluated_first(self):
        self.both("rows = [[1], [2]]\n"
                  "def bump():\n"
                  "    rows.append([100])\n"
                  "    return 0\n"
                  "print(sum((sum(v for v in row) for row in rows), bump()))\n")
        self.both("rows = [[1], [2]]\n"
                  "print(sorted((sum(v for v in row) for row in rows), key=len))\n")

    def test_unpack_target_is_not_exhaustion(self):
        self.both("rows = [[1], [2], [3], [4]]\n"
                  "def bad(x):\n"
                  "    if x == 4:\n"
                  "        raise RuntimeError('boom')\n"
                  "    return x\n"
                  "a, b = (sum(bad(v) for v in row) for row in rows)\n")

    def test_incremental_consumer(self):
        self.both("rows = [[1], [2, 'a']]\n"
                  "print(dict((sum(v for v in row) for row in rows)))\n")


if __name__ == "__main__":
    unittest.main()
