"""Fuzz round 21: the text of a failed unpack (found by differential probing).

CPython's UNPACK_SEQUENCE error carries the counts: `a, b = (1, 2, 3)` prints
"too many values to unpack (expected 2)", a short sequence prints
"not enough values to unpack (expected 2, got 1)", a starred target says
"(expected at least N, got M)", and a non-iterable operand says
"cannot unpack non-iterable int object".  The general path printed shorter texts and
the iter() wording instead, a silent difference on stdout when the program catches
and prints the exception.

Each program is ordinary Python, run against CPython 3.12; the default build and the
forced general build must print the same bytes with the same exit status.
"""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent
CLI = str(ROOT / "ail_chatgpt.py")

UNPACK_ERRORS = r'''
class C:
    def __init__(self):
        self.v = 5
        self.t = (1,)


def take(x):
    try:
        a, b = x
        print("ok", a, b)
    except (ValueError, TypeError) as e:
        print(type(e).__name__, e)


def star(x):
    try:
        a, *b, c = x
        print("ok", a, b, c)
    except (ValueError, TypeError) as e:
        print(type(e).__name__, e)


def main():
    o = C()
    vals = [(1, 2, 3), (1,), (), [9, 8, 7], "a", b"xy", o.v, o.t, None, 1.5, True, o]
    for v in vals:
        take(v)
    for v in vals:
        star(v)
    d = {"short": (1,), "long": (1, 2, 3, 4), "bad": 7}
    for k in d:
        take(d[k])
        star(d[k])
    xs = [o.v, o.t, d["bad"]]
    for x in xs:
        take(x)
        star(x)
    try:
        a, *b, c, d = [1, 2]
        print("ok", a, b, c, d)
    except ValueError as e:
        print(type(e).__name__, e)


main()
'''


def run_py(path):
    r = subprocess.run([sys.executable, "-B", str(path)], capture_output=True, timeout=60)
    return r.returncode, r.stdout


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="ail-fuzz21-")
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
        return subprocess.run([sys.executable, "-B", CLI, "compile", str(path), "--syntax", "python",
                               "-o", str(exe)], cwd=self.dir, capture_output=True, text=True, env=env), exe

    def same(self, src):
        path = self.dir / "ref.py"
        path.write_text(src, encoding="utf-8")
        code, out = run_py(path)
        for general in (False, True):
            built, exe = self.build(src, general)
            self.assertEqual(built.returncode, 0, built.stdout + built.stderr)
            ran = subprocess.run([str(exe)], capture_output=True, timeout=60)
            self.assertEqual(ran.stdout, out, "general" if general else "default")
            self.assertEqual(ran.returncode, code)
        return out


class UnpackErrors(Base):
    def test_error_text_and_non_iterable_wording(self):
        out = self.same(UNPACK_ERRORS)
        self.assertIn(b"ValueError too many values to unpack (expected 2)\n", out)
        self.assertIn(b"ValueError not enough values to unpack (expected 2, got 1)\n", out)
        self.assertIn(b"ValueError not enough values to unpack (expected 2, got 0)\n", out)
        self.assertIn(b"TypeError cannot unpack non-iterable int object\n", out)
        self.assertIn(b"TypeError cannot unpack non-iterable NoneType object\n", out)
        self.assertIn(b"ValueError not enough values to unpack (expected at least 2, got 1)\n", out)
        self.assertIn(b"ValueError not enough values to unpack (expected at least 3, got 2)\n", out)


if __name__ == "__main__":
    unittest.main()
