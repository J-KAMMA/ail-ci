"""INT64_MIN and +-2**63 edges that used to wrap, crash, or stop with the wrong operation named.

Covers math.gcd / math.lcm at INT64_MIN, math.ceil / floor / int(float) / round at and beyond
+-2**63, // / % / divmod with INT64_MIN and -1, -INT64_MIN / abs(INT64_MIN), powers of negative
bases, and int(text) / int(text, base) just inside and outside int64. Every case is checked on
the default typed path, the forced general path, and the opt-in exact mode against CPython.
"""
import contextlib
import io
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent
MAXV = (1 << 63) - 1
MINV = -(1 << 63)

RUN = r"""import sys
import math


class Box:
    def __init__(self, v):
        self.v = v


def run(op, a, b, s, f):
    if op == 0:
        print(math.gcd(a, b))
    elif op == 1:
        print(math.lcm(a, b))
    elif op == 2:
        print(math.ceil(f))
    elif op == 3:
        print(math.floor(f))
    elif op == 4:
        print(int(f))
    elif op == 5:
        print(round(f))
    elif op == 6:
        print(a // b)
    elif op == 7:
        print(a % b)
    elif op == 8:
        q, r = divmod(a, b)
        print(q, r)
    elif op == 9:
        print(-a)
    elif op == 10:
        print(abs(a))
    elif op == 11:
        print(a ** b)
    elif op == 12:
        print(int(s))
    elif op == 13:
        print(int(s, b))
    elif op == 14:
        xs = [a, b]
        print(math.gcd(xs[0], xs[1]))
    elif op == 15:
        d = {0: a}
        print(math.lcm(d[0], b))
    elif op == 16:
        print(math.floor(f) + 0)
    elif op == 17:
        print(math.ceil(f) + 0)
    elif op == 18:
        print(math.ceil(Box(f).v))
    elif op == 19:
        print(math.floor(Box(f).v))
    elif op == 20:
        print(math.floor(a))
    elif op == 21:
        print(math.ceil(a))


def main():
    t = sys.stdin.read().split("\n")
    op = int(t[0])
    p = t[1].split()
    run(op, int(p[0]), int(p[1]), p[2], float(p[3]))


main()"""


def oracle(op, a, b, s, f):
    ns = {}
    exec(RUN.rsplit("\nmain()", 1)[0], ns)
    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        ns["run"](op, a, b, s, f)
    return out.getvalue()


def fits(text):
    import re
    return all(MINV <= int(m) <= MAXV for m in re.findall(r"-?\d+", text))


def env_for(mode):
    env = dict(os.environ)
    for key in ("AIL_UNIFIED_FORCE", "AIL_EXACT_INT", "AIL_BIGINT", "AIL_NO_GENERAL",
                "AIL_UNIFIED", "AIL_QUIET_FALLBACK"):
        env.pop(key, None)
    if mode == "force":
        env["AIL_UNIFIED_FORCE"] = "1"
    elif mode == "exact":
        env["AIL_EXACT_INT"] = "1"
    env["AIL_NO_CACHE"] = "1"
    return env


def build(directory, mode):
    source = Path(directory, "edge_" + mode + ".py")
    exe = Path(directory, "edge_" + mode)
    source.write_text(RUN, encoding="utf-8")
    made = subprocess.run(
        [sys.executable, "-B", str(ROOT / "ail_chatgpt.py"), "compile", source.name,
         "--syntax", "python", "-o", exe.name],
        cwd=directory, capture_output=True, text=True, timeout=900, env=env_for(mode))
    return made, exe


def run(exe, op, a, b, s, f):
    data = "%d\n%d %d %s %r\n" % (op, a, b, s, f)
    r = subprocess.run([str(exe)], input=data, capture_output=True, text=True, timeout=120)
    return r.returncode, r.stdout, r.stderr


# (op, a, b, text, float, operation named when the CPython value leaves int64)
CASES = [
    (0, MINV, 0, "0", 0.0, "math.gcd()"),
    (0, MINV, MINV, "0", 0.0, "math.gcd()"),
    (0, 0, MINV, "0", 0.0, "math.gcd()"),
    (0, MINV, 1, "0", 0.0, None),
    (0, MINV, 2, "0", 0.0, None),
    (0, MINV, 4, "0", 0.0, None),
    (0, MINV, -2, "0", 0.0, None),
    (0, MINV, 3, "0", 0.0, None),
    (0, MINV, MAXV, "0", 0.0, None),
    (0, 12, -18, "0", 0.0, None),
    (0, 0, 0, "0", 0.0, None),
    (1, MINV, 0, "0", 0.0, None),
    (1, 0, MINV, "0", 0.0, None),
    (1, MINV, 1, "0", 0.0, "math.lcm()"),
    (1, MINV, -1, "0", 0.0, "math.lcm()"),
    (1, MINV, 2, "0", 0.0, "math.lcm()"),
    (1, MINV, MINV, "0", 0.0, "math.lcm()"),
    (1, MINV, 3, "0", 0.0, "math.lcm()"),
    (1, 12, -18, "0", 0.0, None),
    (1, MAXV, 1, "0", 0.0, None),
    (1, 0, 0, "0", 0.0, None),
    (2, 0, 0, "0", -2.0 ** 63, None),
    (2, 0, 0, "0", 2.0 ** 63, "math.ceil()"),
    (2, 0, 0, "0", -2.0 ** 63 - 2048.0, "math.ceil()"),
    (3, 0, 0, "0", -2.0 ** 63, None),
    (3, 0, 0, "0", 2.0 ** 63, "math.floor()"),
    (3, 0, 0, "0", -2.0 ** 63 - 2048.0, "math.floor()"),
    (4, 0, 0, "0", -2.0 ** 63, None),
    (4, 0, 0, "0", 2.0 ** 63, "int(float)"),
    (4, 0, 0, "0", -2.0 ** 63 - 2048.0, "int(float)"),
    (5, 0, 0, "0", 2.0 ** 63, "round()"),
    (5, 0, 0, "0", -2.0 ** 63, None),
    (5, 0, 0, "0", 2.5, None),
    (5, 0, 0, "0", -2.5, None),
    (16, 0, 0, "0", 1e300, "math.floor()"),
    (17, 0, 0, "0", 1e300, "math.ceil()"),
    (18, 0, 0, "0", 2.0 ** 63, "math.ceil()"),
    (19, 0, 0, "0", 2.0 ** 63, "math.floor()"),
    (6, MINV, -1, "0", 0.0, "//"),
    (7, MINV, -1, "0", 0.0, None),
    (8, MINV, -1, "0", 0.0, "//"),
    (6, MINV, 2, "0", 0.0, None),
    (7, MINV, 2, "0", 0.0, None),
    (9, MINV, 0, "0", 0.0, "unary - or abs()"),
    (10, MINV, 0, "0", 0.0, "unary - or abs()"),
    (9, MINV + 1, 0, "0", 0.0, None),
    (10, MINV + 1, 0, "0", 0.0, None),
    (11, -2, 63, "0", 0.0, None),
    (11, -2, 64, "0", 0.0, "**"),
    (11, -2, 62, "0", 0.0, None),
    (11, -3, 40, "0", 0.0, "**"),
    (11, -2, 3, "0", 0.0, None),
    (12, 0, 0, str(MINV), 0.0, None),
    (12, 0, 0, "9223372036854775808", 0.0, "int()"),
    (12, 0, 0, "-9223372036854775809", 0.0, "int()"),
    (13, 0, 16, "7fffffffffffffff", 0.0, None),
    (13, 0, 16, "8000000000000000", 0.0, "int()"),
    (13, 0, 10, "-9223372036854775809", 0.0, "int()"),
    (13, 0, 2, "1" + "0" * 63, 0.0, "int()"),
    (14, MINV, 4, "0", 0.0, None),
    (14, MINV, 0, "0", 0.0, "math.gcd()"),
    (15, MINV, 0, "0", 0.0, None),
    (15, MINV, 2, "0", 0.0, "math.lcm()"),
    (20, 9007199254740993, 0, "0", 0.0, None),
    (20, MAXV, 0, "0", 0.0, None),
    (20, MINV, 0, "0", 0.0, None),
    (21, 9007199254740993, 0, "0", 0.0, None),
    (21, MAXV, 0, "0", 0.0, None),
    (21, MINV, 0, "0", 0.0, None),
]


class Int64Edges(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.exe = {}
        for mode in ("default", "force", "exact"):
            made, exe = build(cls.tmp.name, mode)
            if made.returncode:
                raise AssertionError("%s did not build: %s" % (mode, made.stderr[-2000:]))
            cls.exe[mode] = exe

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_each_edge_against_cpython(self):
        checked = {"fits": 0, "beyond": 0}
        for op, a, b, s, f, name in CASES:
            want = oracle(op, a, b, s, f)
            inside = fits(want)
            label = (op, a, b, s, f)
            for mode in ("default", "force", "exact"):
                code, out, err = run(self.exe[mode], op, a, b, s, f)
                if mode == "exact" or inside:
                    self.assertEqual((code, out, err), (0, want, ""), (mode, label))
                else:
                    self.assertEqual((code, out), (1, ""), (mode, label, err))
                    self.assertTrue(err.startswith("OverflowError: integer overflow in "), (mode, label, err))
                    self.assertIsNotNone(name, (mode, label, want, err))
                    self.assertTrue(err.startswith("OverflowError: integer overflow in " + name),
                                    (mode, label, err))
            checked["fits" if inside else "beyond"] += 1
        self.assertGreater(checked["fits"], 25)
        self.assertGreater(checked["beyond"], 20)


COMPREHENSION_RUN = r"""import math


def length(s: str) -> int:
    return len(s)


def floors(xs: list[float]) -> list[int]:
    return [math.floor(x) for x in xs]


def shorten(words: list[str]) -> list[int]:
    return [length(w) for w in words]


def tail(words: list[str]) -> list[int]:
    return [length(w) for w in words[1:]]


print(shorten(["a", "bb", "ccc"]))
print(tail(["a", "bb", "ccc", "dddd"]))
print(floors([1.9, -1.1, 2.0, -0.0]))
print(shorten([]))
"""


class ComprehensionCallSiteKinds(unittest.TestCase):
    def test_typed_path_keeps_each_comprehensions_element_kind(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp, "comp.py")
            source.write_text(COMPREHENSION_RUN, encoding="utf-8")
            want = subprocess.run([sys.executable, str(source)], capture_output=True, text=True,
                                  timeout=120)
            env = env_for("default")
            env["AIL_NO_GENERAL"] = "1"
            made = subprocess.run(
                [sys.executable, "-B", str(ROOT / "ail_chatgpt.py"), "compile", source.name,
                 "--syntax", "python", "-o", "comp"],
                cwd=tmp, capture_output=True, text=True, timeout=900, env=env)
            self.assertEqual(made.returncode, 0, made.stderr[-2000:])
            got = subprocess.run([str(Path(tmp, "comp"))], capture_output=True, text=True,
                                 timeout=120)
            self.assertEqual((got.returncode, got.stdout, got.stderr),
                             (want.returncode, want.stdout, want.stderr))


if __name__ == "__main__":
    unittest.main()
