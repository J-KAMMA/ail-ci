"""Pre-185: range slicing.

`range(10)[2:5]` and every other slice of a range raised `TypeError: 'range' object is not
subscriptable` on both builds (the slice dispatch handled str/list/tuple only).  A range is
sliced as the sequence it denotes: the slice indices are adjusted against the range's count
and mapped back through its start/step, producing a new range exactly as CPython 3.12 does.
The values reach the slice as literals, an argument, a list item, an attribute and a dict
value; empty, negative-step, bool-index and int64-boundary cases are compared with CPython on
both builds.  A slice result whose own start/stop/step would fall outside int64 (only possible
near INT64_MIN/INT64_MAX with the wrong direction) is the AIL int limit and is recorded in
DIFFERENCES, not exercised here.
"""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent
CLI = str(ROOT / "ail_chatgpt.py")

RANGE_SLICE = r"""def show(x):
    print(repr(x), list(x), len(x))


def cut(r, lo, hi, st):
    return r[lo:hi:st]


class C:
    def __init__(self, r):
        self.r = r


def main():
    r = range(10)
    show(r[:])
    show(r[::])
    show(r[2:5])
    show(r[2:5:2])
    show(r[::2])
    show(r[::-1])
    show(r[::-2])
    show(r[8:2:-2])
    show(r[-3:])
    show(r[:-3])
    show(r[100:200])
    show(r[-100:-200])
    show(r[5:2])
    show(r[5:2:-1])
    show(r[2:5:-1])
    show(r[1:1])
    show(r[True:False])
    for rr in (range(0, 10, 3), range(10, 0, -3), range(-5, 5, 2),
               range(5, -5, -2), range(0), range(3, 3), range(1, 2)):
        show(rr[:])
        show(rr[::-1])
        show(rr[1:4])
        show(rr[-4:-1])
        show(rr[::2])
        show(rr[::-2])
    show(range(9223372036854775800, 9223372036854775807)[2:5])
    show(range(9223372036854775800, 9223372036854775807)[::-1])
    show(range(-9223372036854775807 - 1, -9223372036854775800)[2:5])
    show(range(-9223372036854775807 - 1, -9223372036854775800)[::2])
    x = r[2:8:2]
    y = x
    print(x == y, x == range(2, 8, 2), list(x), len(x))
    items = [range(10)]
    show(items[0][2:5])
    d = {"r": range(10)}
    show(d["r"][2:5])
    c = C(range(10))
    show(c.r[2:5])

    def f(q):
        return q[2:5]

    show(f(range(10)))
    print(list(cut(range(10), 2, 8, 2)), list(cut(range(10), 0, 10, -1)))
    lo, hi, st = 2, 8, 2
    print(list(r[lo:hi:st]), list(r[lo:hi]), list(r[lo::st]), list(r[:hi]))


main()
"""


class Pre185Tests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="ail-pre185-")
        self.dir = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def test_range_slicing_matches_cpython_on_both_builds(self):
        ref = self.dir / "ref.py"
        ref.write_text(RANGE_SLICE, encoding="utf-8")
        py = subprocess.run([sys.executable, "-B", str(ref)], capture_output=True, timeout=60)
        self.assertEqual(py.returncode, 0, py.stderr)
        for general in (False, True):
            path = self.dir / "p.py"
            path.write_text(RANGE_SLICE, encoding="utf-8")
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


if __name__ == "__main__":
    unittest.main()
