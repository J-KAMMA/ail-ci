"""fuzz89: bytes/bytearray whitespace split with maxsplit keeps the unsplit remainder.

Found by comparing small bytes programs with CPython on both builds. The general path's
`_ail_b_split_ws` primitive (safetyrt.py) trimmed the outer whitespace off the remainder once
maxsplit was reached, for both split() and rsplit():

    b" a ".split(None, 0)       CPython [b'a ']      AIL [b'a']
    b"  a  b  ".split(None, 1)  CPython [b'a', b'b  ']  AIL [b'a', b'b']
    b" a ".rsplit(None, 0)      CPython [b' a']      AIL [b'a']

CPython's remainder after the last split is the rest of the text, including the whitespace at
the outer edge; only the run separating it from the previous field is dropped. The primitive
now does exactly that (the typed-path loops already did).

The programs below also keep the neighbouring bytes shapes compared: slicing, startswith,
replace, count, comparison and concatenation, and maxsplit reaching the method through an
argument, a list item, an attribute and a dict value.
"""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent
CLI = str(ROOT / "ail_chatgpt.py")


def run_py(path):
    r = subprocess.run([sys.executable, "-B", str(path)], capture_output=True, timeout=60)
    return r.returncode, r.stdout


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="ail-fuzz89-")
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
        built = subprocess.run([sys.executable, "-B", CLI, "compile", str(path), "--syntax", "python",
                                "-o", str(exe)], cwd=self.dir, capture_output=True, text=True, env=env)
        return built, exe

    def same(self, src):
        path = self.dir / "ref.py"
        path.write_text(src, encoding="utf-8")
        code, out = run_py(path)
        self.assertEqual(code, 0)
        for general in (False, True):
            built, exe = self.build(src, general)
            self.assertEqual(built.returncode, 0, built.stdout + built.stderr)
            ran = subprocess.run([str(exe)], capture_output=True, timeout=60)
            self.assertEqual(ran.stdout, out, "general" if general else "default")
            self.assertEqual(ran.returncode, code)
        return out


WS_SPLIT = r'''class Box:
    def __init__(self, n):
        self.n = n


def cut(s, sep, ms):
    return s.split(sep, ms), s.rsplit(sep, ms)


def main():
    xs = [b" a ", b"  a  b  ", b"\t\n a\r b \v\f", b"   ", b""]
    ms = [-1, 0, 1, 2, 3]
    d = {"ms": 1, "sep": None, "sep2": b" "}
    b = Box(2)
    for i in range(len(xs)):
        print(cut(xs[i], None, ms[i]))
        print(cut(xs[i], b" ", ms[i]))
    print(cut(xs[1], None, d["ms"]))
    print(cut(xs[1], d["sep"], d["ms"]))
    print(cut(xs[1], d["sep2"], d["ms"]))
    print(cut(xs[1], None, b.n))
    print(cut(xs[1], b" ", b.n))
    print(xs[1].split(None, ms[2]), xs[1].rsplit(None, ms[2]))
    print(xs[2].split(None, 0), xs[2].rsplit(None, 0))
    print(xs[2].split(None, 1), xs[2].rsplit(None, 1))
    print(b" a ".split(None, 0), b" a ".rsplit(None, 0))
    print(b"  a  b  ".split(None, 1), b"  a  b  ".rsplit(None, 1))
    a = bytearray(b"  a  b  ")
    for n in (-2, -1, 0, 1, 2, 10):
        print(n, a.split(None, n), a.rsplit(None, n), a.split(b" ", n))
    print(bytes(a[1:]), bytes(a[::-1]), a[:0], a[-100:100])


main()
'''

BYTES_SHAPES = r'''def main():
    b = b"abcabcabc"
    print(b[0:0], b[::-1], b[-100:100], b[4:2])
    print(b.startswith(b"", 10, 0), b.endswith(b"", 2, 1), b.startswith(b"cd", -100, 100))
    for n in (-3, -1, 0, 1, 3, 100):
        print(b.replace(b"", b"X", n), b.replace(b"a", b"", n), b.count(b"", 1, 8))
    print(b.split(b"abc"), b.split(b"a", 1), b.replace(b"bc", b"bcbc"))
    print(b < b"abcabcb", b == b"abcabcabc", b >= b"abc", b"\xff" > b"\x00")
    print(b"a" + b"", b"" + b"", b"ab" * 3, (b"" + b"x") + b"y")
    print(bytes(range(256))[250:].count(b""), b"aaa".replace(b"aa", b"b"))


main()
'''


class Fuzz89Tests(Base):
    def test_whitespace_split_maxsplit_remainder(self):
        out = self.same(WS_SPLIT)
        self.assertIn(b"b'a '", out)
        self.assertIn(b"b'b  '", out)

    def test_bytes_shapes_still_match(self):
        self.same(BYTES_SHAPES)


if __name__ == '__main__':
    unittest.main()
