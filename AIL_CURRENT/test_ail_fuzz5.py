"""fuzz5: silent differences found fuzzing number formatting and arithmetic (all CPython-identical now).

1. The general path's float `//`, `%` and `divmod()` took `floor(x / y)` and corrected only the
   remainder's sign. CPython's float_divmod takes the remainder first and snaps the quotient from
   it, so `6.0 // 0.4` is 14.0 (not 15.0), and a ZERO remainder takes the divisor's sign
   (`7.5 % -0.5` is -0.0, `-7.5 % 0.5` is 0.0). The typed path already used that algorithm
   (ail_ffloormod); the boxed runtime (ail__fdivmod / ail__op_fdivmod) and the unified fast path
   now do too.
2. `abs(-0.0)` handed the negative zero back (it lowered to `v < 0 ? -v : v`, and `-0.0 < 0` is
   false); CPython's abs() clears the sign. Both the IR lowering and the legacy emitter now
   normalise a zero to +0.0.
3. Format specs, three ways the padding disagreed with CPython:
   * the '0' flag next to a WRITTEN alignment fills with zeros on that side (`{:<06d}` of 42 is
     '420000', `{:^09.2f}` of 1.5 is '001.50000'); it used to pad with spaces;
   * a '0' fill pads after the sign, including the ' ' flag (`'% 08.3f'` is ' 001.500'), and
     '%-08d' is '255     ' (CPython's %-formatting ignores '0' next to '-'), and a fill character
     makes the '0' the first digit of the width (`{:*<06d}` is '42****');
   * the IR took a spec the three small formatters cannot express (a sign, '#', grouping, a
     non-'d'/'f' type, a fill, '=' or zero-next-to-align) and silently dropped that part: an
     f-string in a three-or-more-piece concatenation printed `f"{n:,d}"` of -1234 as '-1234' and
     `f"{n:<06d}"` of 42 as '000042'. It now leaves those fields to the general formatter.

Each program is built twice (default build, AIL_UNIFIED_FORCE=1 general path) and must print what
CPython prints with the same exit status.
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
    proc = subprocess.run([sys.executable, str(path)], capture_output=True, timeout=120)
    return proc.returncode, proc.stdout


FLOAT_FLOORDIV_MOD = r'''
class Box:
    def __init__(self):
        self.v = 6.0
        self.w = 0.4
        self.z = -0.0
        self.n = -7.5

def pair(x: float, y: float) -> None:
    print(x, y, x // y, x % y, divmod(x, y))

def main():
    print(6.0 // 0.4, 6.0 % 0.4, divmod(6.0, 0.4))
    print(-7.5 // 0.5, -7.5 % 0.5, 7.5 % -0.5, 7.5 // -0.5, -6.0 // -0.4)
    pair(6.0, 0.4)
    pair(-6.0, 0.4)
    pair(7.5, -0.5)
    xs = [6.0, -7.5, -0.0, 1e18]
    ys = [0.4, 0.5, 2.0, 7.0]
    for i in range(4):
        print(xs[i] // ys[i], xs[i] % ys[i], divmod(xs[i], ys[i]))
    d = {"a": 6.0, "b": 0.4, "c": -0.0, "e": -2.0}
    print(d["a"] // d["b"], d["a"] % d["b"], divmod(d["a"], d["b"]))
    print(d["c"] // d["e"], d["c"] % d["e"], divmod(d["c"], d["e"]))
    o = Box()
    print(o.v // o.w, o.v % o.w, divmod(o.v, o.w))
    print(o.z // 2.0, o.z % 2.0, o.n % 0.5, o.n // 0.5)
    print(7.0 // 2, 7 // 2.0, 7.0 % 2, 7 % 2.0, divmod(7.0, 2))
    print(1e18 // 7, 1e18 % 7, divmod(1e18, 7))
    print(-1e18 // 7, -1e18 % 7, divmod(-1e18, 7)[0], divmod(-1e18, 7)[1])
    print(1e300 // 3, 1e300 % 3, -1e300 % 3)
    print(0.0 // 1e308, 0.0 % 1e308, -0.0 // 1e308, -0.0 % 1e308)
    acc = 0.0
    for i in range(-4, 5):
        acc = acc + (i % 3)
    print(acc, acc // 2.5, acc % 2.5, divmod(acc, 2.5))

main()
'''

FLOAT_DIVMOD_SIGNS = r'''
def sign(x: float) -> str:
    if x != 0.0:
        return "nz"
    return "-0" if str(x).startswith("-") else "+0"

def main():
    for x in [0.0, -0.0, 1.0, -1.0, 0.5, -0.5]:
        for y in [1.0, -1.0, 2.0, -2.0, 0.5, -0.5]:
            q = x // y
            r = x % y
            dm = divmod(x, y)
            print(sign(q), sign(r), sign(dm[0]), sign(dm[1]), r == 0.0)
    print(-0.0 // 1.0, -0.0 % 1.0, 0.0 % -1.0, -0.0 // -1.0, 0.0 // -1.0)
main()
'''

ABS_NEG_ZERO = r'''
class C:
    def __init__(self):
        self.v = -0.0
        self.u = 0.0
        self.w = -2.5

def show(x: float) -> None:
    print(repr(abs(x)), repr(x))

def main():
    print(repr(abs(-0.0)), repr(abs(0.0)))
    x = -0.0
    print(repr(abs(x)))
    show(-0.0)
    show(-2.5)
    L = [-0.0, 0.0, -3.0]
    for v in L:
        print(repr(abs(v)))
    d = {"z": -0.0, "o": 0.0}
    print(repr(abs(d["z"])), repr(abs(d["o"])))
    c = C()
    print(repr(abs(c.v)), repr(abs(c.u)), repr(abs(c.w)))
    print(repr(abs(0.0 * -1.0)), repr(abs(-1.0 * 0.0)), repr(abs(-0.0 + 0.0)))
    print(repr(abs(-0.0) + 0.0), repr(abs(-0.0) * 1.0), "%r" % abs(-0.0))
    print(abs(-0.0), abs(0.0), abs(-5), abs(5), abs(-2.5), abs(-0.0) == 0.0)
    print(int(abs(-0.0)), round(abs(-0.0)), format(abs(-0.0), ".1f"), str(abs(-0.0)))

main()
'''

FMT_ZERO_ALIGN = r'''
class C:
    def __init__(self):
        self.n = 42
        self.m = -1234
        self.f = 1.5
        self.z = -0.0

def fi(x: int) -> str:
    return "<" + format(x, "<06d") + ">" + "<" + format(x, "^06d") + ">" + "<" + format(x, ">06d") + ">"

def main():
    n = 42
    m = -1234
    f = 1.5
    z = -0.0
    print("|" + format(n, "<06d") + "|" + format(m, "<06d") + "|" + format(n, "^06d") + "|" + format(m, ">06d") + "|")
    print("|" + "{:<06d}".format(n) + "|" + "{:^06d}".format(m) + "|" + "{:0=6d}".format(m) + "|")
    print("|" + f"{n:<06d}" + "|" + f"{m:^06d}" + "|" + f"{m:0=6d}" + "|" + f"{m:>06d}" + "|")
    print("|" + "{:*<06d}".format(n) + "|" + format(n, "*>06d") + "|" + f"{m:*^07d}" + "|")
    print("|" + format(f, "<08.2f") + "|" + format(z, "^09.2f") + "|" + format(-1.5, "0=8.2f") + "|")
    print("|" + "{:^09.2f}".format(f) + "|" + "{:<010.3f}".format(z) + "|" + f"{f:<08.3f}" + "|")
    print("|" + format(m, "08,d") + "|" + format(m, "<08,d") + "|" + format(m, "=08,d") + "|" + f"{m:^010,d}" + "|")
    print("|% 08.3f|% 08d|%+08d|%- 08d|%08.3f|" % (f, n, n, n, z))
    print("|{: 08.3f}|{: 08d}|{:+09d}|".format(f, n, m))
    print(fi(n))
    L = [n, m]
    print("|" + f"{L[1]:<07d}" + "|" + format(L[0], "^07d") + "|")
    d = {"n": n, "m": m}
    print("|" + "{:<07d}".format(d["m"]) + "|" + f"{d['n']:>07d}" + "|")
    c = C()
    print("|" + f"{c.m:<07d}" + "|" + format(c.f, "^010.2f") + "|" + f"{-0.5:0=7.2f}" + "|")

main()
'''

PCT_MINUS_ZERO = r'''
def main():
    n = 42
    m = -1234
    x = 1.5
    s = "ab"
    print("|%-08d|%08d|%-08d|" % (n, n, m))
    print("|%-09.2f|%-08.3f|%08.3f|" % (x, x, x))
    print("|%-6s|%06d|%-06d|" % (s, n, n))
    L = [n, m]
    print("|%-06d|%06d|" % (L[0], L[1]))
    d = {"n": n, "x": x}
    print("|% 08d|%08.2f|%- 08d|" % (d["n"], d["x"], d["n"]))
    for v in [0, -1, 5, -5]:
        print("%d %05d %-5d|%+d % 5d" % (v, v, v, v, v))
main()
'''

IR_FSTRING_GENERAL_SPECS = r'''
class C:
    def __init__(self):
        self.n = 255
        self.m = -1234

def tag(x: int, y: int) -> str:
    return "[" + f"{x:+d}" + "|" + f"{y:,d}" + "|" + f"{x:#x}" + "]"

def main():
    n = 255
    m = -1234
    x = 1.5
    print("|" + f"{n:+d}" + "|" + f"{m:+d}" + "|" + f"{n: d}" + "|")
    print("|" + f"{n:#x}" + "|" + f"{n:#o}" + "|" + f"{n:#b}" + "|" + f"{m:x}" + "|")
    print("|" + f"{m:,d}" + "|" + f"{m:_d}" + "|" + f"{m:08,d}" + "|" + f"{n:^010,d}" + "|")
    print("|" + f"{x:+.2f}" + "|" + f"{x:,.3f}" + "|" + f"{x: e}" + "|" + f"{x:%}" + "|")
    print(tag(n, m), tag(-7, 1234567))
    L = [n, m]
    print("|" + f"{L[0]:+d}" + "|" + f"{L[1]:,d}" + "|" + "{:,d}".format(L[1]) + "|")
    d = {"n": n, "m": m}
    print("|" + f"{d['n']:#06x}" + "|" + f"{d['m']:_d}" + "|")
    c = C()
    print("|" + f"{c.n:+d}" + "|" + f"{c.m:,d}" + "|" + format(c.m, "+08,d") + "|")
    print("|%+d|% d|%08d|%x|" % (n, n, m, n))

main()
'''


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="ail-fuzz5-")
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
        for general in (False, True):
            built, exe = self.build(src, general)
            self.assertEqual(built.returncode, 0, built.stdout + built.stderr)
            ran = subprocess.run([str(exe)], capture_output=True, timeout=120)
            self.assertEqual(ran.stdout, out, "general" if general else "default")
            self.assertEqual(ran.returncode, code)
        return out

    def refused(self, src, word):
        path = self.dir / "ref.py"
        path.write_text(src, encoding="utf-8")
        for general in (False, True):
            built, _ = self.build(src, general)
            self.assertNotEqual(built.returncode, 0, "built a program this compiler refuses")
            self.assertIn(word, built.stdout + built.stderr)


class FloatFloorDivMod(Base):
    """Float `//`, `%` and `divmod()`: the quotient comes from the remainder, and a zero
    remainder takes the divisor's sign (the general path's floor(x / y) did neither)."""

    def test_quotient_and_sign(self):
        out = self.same(FLOAT_FLOORDIV_MOD)
        self.assertIn(b"14.0 0.3999999999999997 (14.0, 0.3999999999999997)", out)
        self.assertIn(b"7.5 -0.5 -15.0 -0.0 (-15.0, -0.0)", out)

    def test_zero_signs_matrix(self):
        out = self.same(FLOAT_DIVMOD_SIGNS)
        self.assertIn(b"-0 +0 -0 +0 True", out)
        self.assertIn(b"+0 -0 +0 -0 True", out)


class AbsNegativeZero(Base):
    """abs(-0.0) is 0.0, through every route a float can take into abs()."""

    def test_abs(self):
        out = self.same(ABS_NEG_ZERO)
        self.assertTrue(out.startswith(b"0.0 0.0\n0.0\n"))
        self.assertIn(b"0.0 0.0 5 5 2.5 True\n", out)


class FormatSpecZeroFill(Base):
    """The '0' flag with a written alignment, a fill character, grouping and the ' ' sign."""

    def test_int_and_float(self):
        out = self.same(FMT_ZERO_ALIGN)
        self.assertIn(b"|420000|-12340|004200|0-1234|\n", out)
        self.assertIn(b"|420000|-12340|-01234|\n", out)
        self.assertIn(b"|42****|****42|*-1234*|\n", out)
        self.assertIn(b"| 001.500| 0000042|+0000042| 42     |-000.000|\n", out)

    def test_percent_minus_and_zero(self):
        out = self.same(PCT_MINUS_ZERO)
        self.assertIn(b"|42      |00000042|-1234   |\n", out)
        self.assertIn(b"|1.50     |1.500   |0001.500|\n", out)

    def test_fstring_general_specs_in_a_concatenation(self):
        out = self.same(IR_FSTRING_GENERAL_SPECS)
        self.assertIn(b"|+255|-1234| 255|\n", out)
        self.assertIn(b"|0xff|0o377|0b11111111|-4d2|\n", out)
        self.assertIn(b"[-7|1,234,567|-0x7]", out)


if __name__ == "__main__":
    unittest.main()
