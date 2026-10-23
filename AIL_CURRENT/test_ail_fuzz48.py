"""fuzz48: range equality compared by identity, not by the sequence (the general path).

`range(0, 10, 2) == range(0, 9, 2)` printed False where CPython prints True: ail_obj_eq_raw
fell through to the default `==` case for AIL_T_RANGE. CPython compares the two sequences
(equal lengths, then equal start; every empty range equals every other empty range and a
length-1 range is fixed by its start alone),
so the runtime now does the same. The values reach the comparison as arguments, list items, a
dict value and an attribute, and both builds are compared with CPython.
"""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent
CLI = str(ROOT / "ail_chatgpt.py")

RANGE_EQ = r"""class C:
    def __init__(self, r):
        self.r = r

def eq(a, b):
    print(a == b, a != b)

def main():
    eq(range(0, 10, 2), range(0, 9, 2))
    eq(range(0, 10, 2), range(0, 11, 2))
    eq(range(5, 0, -1), range(4, -1, -1))
    eq(range(5, 0, -1), range(5, 0, -2))
    eq(range(0), range(2, 2))
    eq(range(0, 0, 2), range(5, 5, 3))
    eq(range(3, 3, -1), range(-7, -7, 9))
    eq(range(1, 2), range(1, 1))
    eq(range(0, 1, 2), range(0, 1, 1))
    eq(range(0, 1, 2), range(0, 5, 7))
    eq(range(0, 1, 2), range(1, 2, 2))
    eq(range(5, 4, -1), range(5, 4, -7))
    eq(range(-9223372036854775807, 9223372036854775807, 3),
       range(-9223372036854775807, 9223372036854775807, 3))
    eq(range(-9223372036854775807, 9223372036854775807, 3),
       range(-9223372036854775807, 9223372036854775806, 3))
    c = C(range(5, 0, -1))
    xs = [range(0), range(3, 0, -1)]
    d = {"r": range(2, 12, 2)}
    a = range(5, 0, -1)
    eq(c.r, a)
    eq(xs[0], range(9, 9))
    eq(xs[1], range(3, 0, -1))
    eq(d["r"], range(2, 12, 2))
    eq(d["r"], range(0, 10, 2))
    eq([range(2)], [range(0, 2)])
    print(range(2) in [range(0, 2)], range(3) in [range(0, 2)])
main()
"""

RANGE_OPS = r"""def main():
    print(list(range(5, -6, -1)))
    print(list(range(5, 0, -2)))
    print(list(range(0, 0)))
    print(list(range(3, 3, -1)))
    print(len(range(5, -6, -1)), len(range(0, 0)), len(range(5, 1, 2)))
    r = range(2, 20, 3)
    print(len(r), r[0], r[3], r[-1], r[-5])
    print(list(reversed(range(5))))
    print(list(reversed(range(1, 10, 2))))
    print(list(reversed(range(10, 0, -3))))
    print(list(reversed(range(0))))
    print(list(zip([1, 2, 3], "ab")))
    print(list(zip([1], [])))
    print(list(enumerate("abc")))
    print(list(enumerate("abc", 10)))
    print(list(enumerate([], 5)))
    print(list(enumerate([7, 8], -3)))
    print(list(enumerate(range(3), 2)))
    print(list(zip(range(3), reversed(range(3)))))
    print([(i, j) for i in range(2) for j in range(i, 3)])
main()
"""


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="ail-fuzz48-")
        self.dir = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def same(self, src):
        ref = self.dir / "ref.py"
        ref.write_text(src, encoding="utf-8")
        py = subprocess.run([sys.executable, "-B", str(ref)], capture_output=True, timeout=60)
        for general in (False, True):
            path = self.dir / "p.py"
            path.write_text(src, encoding="utf-8")
            env = dict(os.environ, AIL_NO_CACHE="1", AIL_QUIET_FALLBACK="1")
            env.pop("AIL_UNIFIED_FORCE", None)
            if general:
                env["AIL_UNIFIED_FORCE"] = "1"
            exe = self.dir / ("exe_g" if general else "exe_d")
            built = subprocess.run([sys.executable, "-B", CLI, "compile", str(path),
                                    "--syntax", "python", "-o", str(exe)],
                                   cwd=self.dir, capture_output=True, text=True, env=env)
            self.assertEqual(built.returncode, 0, built.stdout + built.stderr)
            ran = subprocess.run([str(exe)], capture_output=True, timeout=60)
            self.assertEqual(ran.stdout, py.stdout, "general" if general else "default")
            self.assertEqual(ran.returncode, py.returncode)
        return py.stdout


class RangeEquality(Base):
    def test_equality_sequence_boundaries(self):
        out = self.same(RANGE_EQ)
        self.assertIn(b"True False\n", out)     # equal ranges: == True, != False
        self.assertIn(b"False True\n", out)

    def test_range_operations_still_match(self):
        self.same(RANGE_OPS)


if __name__ == "__main__":
    unittest.main()
