"""fuzz68: container conversions that printed CPython's text differently.

* A list display with values of different types (`[1, "a", None, True]`) beside any tuple use
  was lowered with the first element's type (list[int]); str() / print of it then used str()
  on every element, so `['a']` printed as `[a]` (CPython: `[1, 'a', None, True]`).  The tuple
  pass now leaves a display whose element types differ (only int + float widen) as written,
  so the general path builds CPython's mixed list; the same for a set / dict display and for
  None beside another type.  The value is tried through an argument, a list item, an attribute
  and a dict value.

Each program is built by default and with the general path forced (AIL_UNIFIED_FORCE=1) and
must print what CPython prints with the same exit status.
"""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent
CLI = str(ROOT / "ail_chatgpt.py")

MIXED_SRC = r"""def show(xs):
    print(xs)
    print(str(xs))


class Box:
    def __init__(self, v):
        self.v = v


def build(v):
    return [v, "a", None, True]


def main():
    t = (1, 2)
    print(t)
    mixed = [1, "a", None, True]
    show(mixed)
    show(build(2))
    b = Box([3, "c"])
    print(b.v)
    print(str(b.v))
    d = {"k": [4, "d"]}
    print(d["k"])
    print(str(d["k"]))
    rows = [[1, "e"], [2, "f"]]
    print(rows[1])
    print(str(rows[0]))
    s = {1, "a", 2}
    print(len(s), 1 in s, "a" in s)
    dm = {"a": 1, "b": "x", "c": 2.5}
    print(dm)
    for xs in ([True, 1], [None, 1], [1, None]):
        print(xs)
        print(str(xs))


main()
"""

HOMOGENEOUS_SRC = r"""def main():
    t = (1,)
    print(t)
    print([1, 2.5, 3], str([1, 2.5, 3]))
    print([True, False], ["a", "b"], [])
    print([[1], [2, 3]], [[], [1]])
    print(sorted({3, 1, 2}), list({"b": 2, "a": 1}))
    print(dict([("x", 1), ("y", 2)]), tuple(iter([4, 5])))


main()
"""


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="ail-fuzz68-")
        self.dir = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def build(self, src, general):
        path = self.dir / "p.py"
        path.write_text(src, encoding="utf-8")
        env = dict(os.environ, AIL_NO_CACHE="1", AIL_QUIET_FALLBACK="1")
        env.pop("AIL_UNIFIED_FORCE", None)
        if general:
            env["AIL_UNIFIED_FORCE"] = "1"
        exe = self.dir / ("exe_g" if general else "exe_d")
        built = subprocess.run([sys.executable, "-B", CLI, "compile", str(path), "--syntax", "python", "-o", str(exe)],
                               cwd=self.dir, capture_output=True, text=True, env=env)
        return built, exe

    def same(self, src):
        path = self.dir / "ref.py"
        path.write_text(src, encoding="utf-8")
        want = subprocess.run([sys.executable, "-B", str(path)], capture_output=True, text=True, timeout=120)
        self.assertEqual(want.returncode, 0, want.stderr)
        for general in (False, True):
            built, exe = self.build(src, general)
            self.assertEqual(built.returncode, 0, built.stdout + built.stderr)
            got = subprocess.run([str(exe)], capture_output=True, text=True, timeout=120)
            label = "general" if general else "default"
            self.assertEqual(got.stdout, want.stdout, label)
            self.assertEqual(got.returncode, 0, label)
        return want.stdout


class ContainerConversions(Base):
    def test_mixed_list_repr_after_tuple_pass(self):
        out = self.same(MIXED_SRC)
        self.assertIn("[1, 'a', None, True]\n", out)
        self.assertIn("[3, 'c']\n", out)
        self.assertIn("[4, 'd']\n", out)

    def test_homogeneous_lists_still_build(self):
        out = self.same(HOMOGENEOUS_SRC)
        self.assertIn("[1, 2.5, 3]\n", out)


if __name__ == "__main__":
    unittest.main()
