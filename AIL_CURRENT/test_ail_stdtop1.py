"""decimal.Decimal on the general path (stdtop.py + prelude_decimal.py), compared with CPython 3.12's C decimal.

Three layers:

* the prelude (prelude_decimal.py) is plain Python, so it runs under CPython next to decimal.Decimal: generated
  operations in generated contexts (precision, rounding mode, exponent limits) must agree on the value, its
  repr / str, and the class and text of the exception when there is one;
* ordinary Python programs are compiled with the default build and with AIL_UNIFIED_FORCE=1 (the general path),
  run on generated stdin and must print the same bytes as CPython and exit with the same status;
* what is not built is refused at compile time by name (`decimal.X is not supported`, with `write instead:`), and a
  program that does not use decimal keeps the text it has.

Declared differences (stdtop.py docstring): the traps and flags of a context are not kept (refused by name),
`Decimal ** Decimal` with a non-integer exponent and `Decimal.ln / exp / log10` are refused or stop with a
RuntimeError, a power that underflows far outside the default exponent range may round differently.
"""
import os
import random
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent
PKG = ROOT / "python" / "pkg-v12"
for each in (str(PKG), str(ROOT)):
    if each not in sys.path:
        sys.path.insert(0, each)

MONEY = r'''
import sys
from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP, ROUND_DOWN, ROUND_FLOOR, InvalidOperation, DecimalException, getcontext, localcontext
import decimal

CENT = Decimal("0.01")


@dataclass
class Line:
    name: str
    price: Decimal
    qty: int

    def total(self) -> Decimal:
        return (self.price * self.qty).quantize(CENT, rounding=ROUND_HALF_UP)


def parse(text: str) -> Decimal:
    try:
        return Decimal(text.strip())
    except InvalidOperation:
        return Decimal(0)


def main() -> None:
    n = int(sys.stdin.readline() or "0")
    rest = sys.stdin.read().split()
    lines = [Line("L%d" % i, parse(t), (i % 5) + 1) for i, t in enumerate(rest)]
    totals = {l.name: l.total() for l in lines}
    print(totals)
    grand = sum(totals.values(), Decimal(0))
    print(f"${grand:,.2f}", "%s" % grand, "{:>12}".format(grand), format(grand, ".1f"), "%.2f" % grand)
    tax = (grand * Decimal("0.0825")).quantize(CENT, ROUND_HALF_UP)
    print(tax, grand + tax, (grand + tax) / 3, (grand + tax) // 3, (grand + tax) % 3, divmod(grand + tax, 7))
    prices = sorted(parse(t) for t in rest)
    print(prices, max(prices) if prices else None, min(prices) if prices else None, sum(prices))
    print(Decimal(1) / Decimal(3), Decimal(2) ** 100, Decimal("1.1") ** 10, Decimal("2") ** -3, Decimal(10).sqrt())
    print(Decimal("0.1") * 3 == Decimal("0.3"), Decimal(3) > 2, 2 < Decimal(3), Decimal(3) == 3, Decimal("1.0") == 1.0)
    print(round(Decimal("2.5")), round(Decimal("3.5")), round(Decimal("2.675"), 2), int(Decimal("-7.9")), float(Decimal("0.1")))
    print(Decimal(0.1), Decimal("1e5"), Decimal("1E-7"), Decimal("123.4500").normalize(), Decimal("1e2").to_integral_value())
    acc = Decimal(0)
    for i in range(n):
        acc += Decimal(i) / Decimal(7)
    print(acc)
    getcontext().prec = 10
    print(Decimal(1) / Decimal(7), Decimal(2).sqrt(), Decimal("123456789012") + 1)
    with localcontext() as ctx:
        ctx.prec = 5
        ctx.rounding = ROUND_DOWN
        print(Decimal(2) / Decimal(3), Decimal("123456789") + 0)
    getcontext().rounding = ROUND_FLOOR
    print(Decimal(-1) / Decimal(3), -Decimal(0), Decimal("-0") + Decimal("0"))
    try:
        Decimal(1) / Decimal(0)
    except decimal.DivisionByZero:
        print("div0")
    try:
        print(Decimal(0) / Decimal(0))
    except decimal.InvalidOperation as e:
        print("undefined", e)
    try:
        print(divmod(Decimal(3), 0))
    except DecimalException as e:
        print(type(e).__name__, e)
    except ZeroDivisionError as e:
        print("zde", e)
    try:
        print(Decimal("9e999999") * 10)
    except decimal.Overflow as e:
        print("overflow", e)
    print(isinstance(grand, Decimal), type(grand).__name__, bool(Decimal(0)), bool(Decimal("0.0001")))


main()
'''

EDGES = r'''
import sys
from decimal import Decimal, InvalidOperation, getcontext, ROUND_UP, ROUND_CEILING, ROUND_05UP, ROUND_HALF_DOWN


def show(label, f):
    try:
        v = f()
        print(label, "->", repr(v) if not isinstance(v, (int, float, bool, str, tuple, list)) else v)
    except Exception as e:
        print(label, "!!", type(e).__name__, e)


def main():
    for line in sys.stdin.read().split("\n"):
        show("new " + repr(line), lambda: Decimal(line))
        show("  neg", lambda: -Decimal(line))
        show("  q", lambda: Decimal(line).quantize(Decimal("0.01")))
        show("  sqrt", lambda: Decimal(line).sqrt())
        show("  int", lambda: int(Decimal(line)))
        show("  float", lambda: float(Decimal(line)))
        show("  fmt", lambda: format(Decimal(line), "+012.3f"))
        show("  eng", lambda: Decimal(line).to_eng_string())
        show("  mix", lambda: (Decimal(line) + 1, Decimal(line) * 2, Decimal(line) / 3, Decimal(line) > 0))
    show("float", lambda: Decimal(0.1))
    show("float2", lambda: Decimal(-1e-320))
    show("float3", lambda: Decimal(1.7976931348623157e308))
    show("float4", lambda: Decimal(float("inf")))
    show("float6", lambda: Decimal(-0.0))
    show("tuple", lambda: Decimal((1, (3, 1, 4), -2)))
    show("tuple2", lambda: Decimal((0, (1, 2), "F")))
    show("tuple4", lambda: Decimal((2, (1,), 0)))
    show("list", lambda: Decimal([0, [1, 5], 3]))
    show("none", lambda: Decimal(None))
    show("bool", lambda: Decimal(True))
    show("big", lambda: Decimal(2 ** 100) * Decimal(2 ** 100))
    show("cmp1", lambda: Decimal("1.0") == 1.0)
    show("cmp2", lambda: Decimal("0.1") == 0.1)
    show("cmp4", lambda: Decimal(1) < "x")
    show("cmp5", lambda: Decimal("NaN") == Decimal("NaN"))
    show("cmp6", lambda: Decimal("NaN") < 1)
    show("add_float", lambda: Decimal(1) + 1.5)
    show("radd_float", lambda: 1.5 + Decimal(1))
    show("mul_str", lambda: Decimal(1) * "a")
    show("radd_list", lambda: [1] + Decimal(1))
    show("ratio", lambda: Decimal("3.14").as_integer_ratio())
    show("hash", lambda: hash(Decimal("1.5")) == hash(1.5))
    show("hash2", lambda: hash(Decimal(7)) == hash(7))
    show("hash3", lambda: len({Decimal("1.0"), Decimal("1.00"), Decimal(1), 1}))
    show("divmod0", lambda: divmod(Decimal(3), 0))
    show("mod0", lambda: Decimal(3) % 0)
    show("pow0", lambda: Decimal(0) ** 0)
    show("pow-1", lambda: Decimal(0) ** -1)
    show("pow big", lambda: Decimal(10) ** 1000000)
    show("pow neg", lambda: Decimal("0.5") ** -3)
    show("pow one", lambda: Decimal("1.000") ** 5)
    show("pow int", lambda: Decimal(4) ** Decimal(2))
    show("ovf", lambda: Decimal("9e999999") * 10)
    show("round big", lambda: round(Decimal("1e30")))
    show("quant err", lambda: Decimal("1e30").quantize(Decimal("0.01")))
    show("max", lambda: Decimal("NaN").max(Decimal(3)))
    show("round n", lambda: round(Decimal("123.456"), -1))
    show("round n2", lambda: round(Decimal("123.456"), 5))
    show("prec", lambda: getcontext().prec)
    getcontext().prec = 3
    show("prec3", lambda: Decimal("1234.5678") + 0)
    show("prec3b", lambda: Decimal("1234.5678") * Decimal("0.001"))
    show("prec3c", lambda: +Decimal("-0"))
    getcontext().rounding = ROUND_UP
    show("up", lambda: Decimal(1) / Decimal(3))
    getcontext().rounding = ROUND_CEILING
    show("ceil", lambda: Decimal(-1) / Decimal(3))
    getcontext().rounding = ROUND_05UP
    show("05up", lambda: Decimal(10) / Decimal(7))
    getcontext().rounding = ROUND_HALF_DOWN
    show("hd", lambda: Decimal("2.5") + Decimal("0.0005"))
    try:
        getcontext().prec = 0
    except ValueError as e:
        print("prec 0:", e)
    try:
        getcontext().rounding = "ROUND_NOPE"
    except TypeError as e:
        print("rounding:", e)


main()
'''


MATHS = r'''
import math
from decimal import Decimal


def t(label, f):
    try:
        print(label, f())
    except Exception as e:
        print(label, "!!", type(e).__name__, e)


d = Decimal("4.5")
t("sqrt", lambda: math.sqrt(d))
t("log10", lambda: math.log10(Decimal(100)))
t("isnan", lambda: (math.isnan(d), math.isnan(Decimal("NaN")), math.isinf(Decimal("Infinity")), math.isfinite(d)))
t("fsum", lambda: math.fsum([d, Decimal(1)]))
t("pow2", lambda: pow(Decimal(2), 3))
t("pow float", lambda: math.pow(d, 2))
t("abs", lambda: abs(Decimal("-2.5")))
t("isclose", lambda: math.isclose(d, Decimal("4.5")))
t("max key", lambda: max([Decimal(1), Decimal(3)], key=lambda x: -x))
t("floor", lambda: (math.floor(Decimal("-2.5")), math.ceil(Decimal("-2.5")), math.floor(Decimal("2.5")), math.ceil(Decimal("2.5"))))
t("range", lambda: list(range(int(d))))
t("index", lambda: [10, 20, 30][int(Decimal("1.9"))])
t("round digits", lambda: (round(Decimal("2.675"), 2), round(Decimal("1234.5"), -2), round(d)))
t("mul int", lambda: (d * 2, 2 * d, d + 1, 1 + d, d - 1, 1 - d, 3 / d, 3 // d, 3 % d))
t("bool", lambda: (bool(Decimal(0)), bool(d), not d))
t("in", lambda: (Decimal(3) in [Decimal(1), Decimal(3)], Decimal(3) in {Decimal(3)}, [Decimal(1), Decimal(2)].index(Decimal(2))))
t("cmp chain", lambda: Decimal(1) < Decimal(2) < Decimal(3))
t("str concat", lambda: "v=" + str(d) + repr(d))
t("join", lambda: ",".join(str(x) for x in [Decimal(1), Decimal("2.50")]))
t("int/float conv", lambda: (int(d), float(d)))
t("isinstance", lambda: (isinstance(d, Decimal), isinstance(1, Decimal), type(d) is Decimal, type(d) == Decimal))
t("eq none", lambda: (d == None, d != None, d is None))
t("hash", lambda: {d: 1}.get(Decimal("4.50")))
t("min mixed", lambda: (min(Decimal(3), 2), max(2.5, Decimal(3))))
t("divmod", lambda: divmod(d, 2))
t("neg zero", lambda: (-Decimal(0), -Decimal("0.0"), +Decimal("-0")))

for dd in [Decimal("2.1"), Decimal("-2.5"), Decimal("2.9"), Decimal("-0.1"), Decimal("7"), Decimal("1e3")]:
    print(dd, math.floor(dd), math.ceil(dd), math.trunc(dd), int(dd), round(dd), math.floor(float(dd)), math.ceil(float(dd)))
from math import floor as fl, log10 as lg
print(fl(Decimal("-0.5")), lg(Decimal(1000)), math.floor(7), math.ceil(2.5), math.sqrt(Decimal(16)), math.log(Decimal(8), 2))
'''


def money_inputs():
    rnd = random.Random(11)
    out = ["0\n", "3\n19.99 0.005 x 1e2 -2.50 7\n", "20\n"]
    words = ["0.10", "2.675", "1e3", "abc", "-0.005", "1234567.891", "NaN", "0", "99.995", "12"]
    for _ in range(3):
        out.append("%d\n%s\n" % (rnd.randint(0, 40), " ".join(rnd.choice(words) for _ in range(rnd.randint(1, 12)))))
    return out


EDGE_LINES = "\n".join([
    "1", "-1.5", "  2.50  ", "1e5", "1E-7", "0", "-0", ".5", "5.", "1_000.5", "1__0", "_1", "\u0661\u0662\u0663", "1.5e",
    "e5", "+", "-", "NaN", "-NaN123", "sNaN", "sNaN7", "Infinity", "-inf", "infinit", "1e999999999999999999999",
    "1e-999999999999999999999", "0.000001234", "12345678901234567890123456789012345.6789", " ", "abc", "1,5", "0x10",
    "\uff11\uff12", "9" * 40, "0.1" + "0" * 30 + "1"]) + "\n"


def compile_python(directory, text, name, **env):
    source, exe = Path(directory, name + ".py"), Path(directory, name)
    source.write_text(text, encoding="utf-8")
    built = subprocess.run([sys.executable, "-B", str(ROOT / "ail_chatgpt.py"), "compile", source.name, "--syntax", "python",
                            "-o", exe.name], cwd=directory, capture_output=True, text=True, timeout=1800,
                           env=dict(os.environ, **env))
    return built, source, exe


class PreludeDecimal(unittest.TestCase):
    """prelude_decimal.py against the C decimal module, in generated contexts."""

    MODES = ["ROUND_UP", "ROUND_DOWN", "ROUND_CEILING", "ROUND_FLOOR", "ROUND_HALF_UP", "ROUND_HALF_DOWN",
             "ROUND_HALF_EVEN", "ROUND_05UP"]
    POOL = ["0", "-0", "1", "-1", "2", "3", "7", "10", "1.5", "-1.5", "0.1", "0.5", "2.5", "-2.5", "0.005", "2.675", "123.456",
            "-123.456", "1e5", "1E-5", "1e-7", "12345678901234567890.123456789", "9.99", "99.995", "0.000001", "0.0000001",
            "1e999999", "5e-1000000", "9.999999999999999999999999999", "3.14159265358979323846264338327950288", "100", "1E+2",
            "0E-10", "0.00", "1.10", "1.100", "NaN", "-NaN", "sNaN", "NaN123", "sNaN7", "Infinity", "-Infinity", "inf", "1000000",
            "999999.5", "0.25", "12.5", "99999999999999999999999999999", "0.3333333333333333333333333333", "-0.0", "5E+3"]
    SPECS = ["", ".2f", ",.2f", "10.3f", "<10", ">10.1f", "^12.2e", "+.3g", " f", "010.2f", ".0f", ".0e", "%", ".1%", "*^15",
             "=+10.2f", ",", "08", "E", ".5G", "#.0f", "z.1f", "n", ".3n", "015,.2f", ".30f", "_", ".1", "q", "10.", ".f"]

    def value(self, rnd):
        k = rnd.random()
        if k < 0.6:
            return rnd.choice(self.POOL)
        if k < 0.8:
            return str(rnd.randint(-10 ** rnd.randint(1, 30), 10 ** rnd.randint(1, 30)))
        digits = "".join(rnd.choice("0123456789") for _ in range(rnd.randint(1, 35)))
        return ("-" if rnd.random() < 0.3 else "") + digits + "E" + str(rnd.randint(-40, 40))

    @staticmethod
    def attempt(f):
        try:
            return ("ok", f())
        except BaseException as e:      # the class and the text are part of what must agree
            return ("err", type(e).__name__, str(e))

    def test_matches_decimal(self):
        import decimal
        import math
        import prelude_decimal as P
        sys.set_int_max_str_digits(0)

        def norm(v):
            if isinstance(v, (decimal.Decimal, P.Decimal)):
                return "D:%s|%r" % (v, v)
            if isinstance(v, (tuple, list)):
                return tuple(norm(x) for x in v)
            if isinstance(v, float):
                return "F:" + repr(v)
            return v

        def setctx(mod, prec, rounding, emin, emax, caps):
            c = mod.getcontext()
            if mod is decimal:
                c.prec, c.rounding, c.Emin, c.Emax, c.capitals = prec, rounding, emin, emax, caps
            else:
                for name, value in (("prec", prec), ("rounding", rounding), ("Emin", emin), ("Emax", emax), ("capitals", caps)):
                    P._ail_dec_set(c, name, value)

        rnd = random.Random(20261030)
        ints = [0, 1, -1, 2, 3, 7, 10, -5, 12345678901234567890, 2 ** 70]
        floats = [0.5, 0.1, -2.0, 1e300, float("inf"), float("nan"), 3.0, -0.0]
        kinds = ["bin"] * 4 + ["un"] * 3 + ["q", "fmt", "cmp", "pow", "ctor", "conv", "mixed"]
        checked = 0
        for it in range(240):
            prec = rnd.choice([1, 2, 3, 5, 9, 28, 28, 28, 50])
            rounding = rnd.choice(self.MODES + ["ROUND_HALF_EVEN"] * 4)
            small = rnd.random() < 0.2
            emin, emax = (rnd.choice([-20, -5, -1]), rnd.choice([20, 5, 1])) if small else (-999999, 999999)
            caps = rnd.choice([0, 1, 1])
            kind = rnd.choice(kinds)
            if kind == "pow" and small:
                kind = "bin"
            a, b = self.value(rnd), self.value(rnd)
            seed = rnd.random()

            def case(mod):
                r2 = random.Random(seed)
                A, B = mod.Decimal(a), mod.Decimal(b)
                out = []
                if kind == "bin":
                    for name, fn in [("+", lambda x, y: x + y), ("-", lambda x, y: x - y), ("*", lambda x, y: x * y),
                                     ("/", lambda x, y: x / y), ("//", lambda x, y: x // y), ("%", lambda x, y: x % y),
                                     ("divmod", divmod), ("max", lambda x, y: x.max(y)), ("min", lambda x, y: x.min(y)),
                                     ("compare", lambda x, y: x.compare(y)), ("sq", lambda x, y: x.same_quantum(y))]:
                        out.append((name, self.attempt(lambda: norm(fn(A, B)))))
                elif kind == "un":
                    for name, fn in [("neg", lambda x: -x), ("pos", lambda x: +x), ("abs", abs), ("sqrt", lambda x: x.sqrt()),
                                     ("normalize", lambda x: x.normalize()), ("tiv", lambda x: x.to_integral_value()),
                                     ("tie", lambda x: x.to_integral_exact()), ("str", str), ("repr", repr),
                                     ("eng", lambda x: x.to_eng_string()), ("adjusted", lambda x: x.adjusted()), ("int", int),
                                     ("float", float), ("round", round), ("floor", math.floor), ("ceil", math.ceil),
                                     ("bool", bool), ("hash", lambda x: hash(x) if not x.is_nan() else 0),
                                     ("ratio", lambda x: x.as_integer_ratio()), ("round2", lambda x: round(x, 2)),
                                     ("round-3", lambda x: round(x, -3)),
                                     ("is", lambda x: (x.is_nan(), x.is_snan(), x.is_qnan(), x.is_infinite(), x.is_finite(),
                                                       x.is_zero(), x.is_signed(), x.is_normal(), x.is_subnormal())),
                                     ("copy_abs", lambda x: x.copy_abs()), ("copy_negate", lambda x: x.copy_negate())]:
                        out.append((name, self.attempt(lambda: norm(fn(A)))))
                elif kind == "q":
                    m = r2.choice(self.MODES)
                    for name, fn in [("q", lambda x, y: x.quantize(y)), ("qm", lambda x, y: x.quantize(y, rounding=m)),
                                     ("tivm", lambda x, y: x.to_integral_value(m))]:
                        out.append((name, self.attempt(lambda: norm(fn(A, B)))))
                    e = r2.choice(["0.01", "1", "1e1", "0.1", "1e-3", "0.0001", "1e5", "1E-30", "1e2"])
                    out.append(("qe", self.attempt(lambda: norm(A.quantize(mod.Decimal(e), rounding=m)))))
                elif kind == "fmt":
                    for sp in self.SPECS:
                        out.append((sp, self.attempt(lambda: format(A, sp))))
                elif kind == "cmp":
                    for name, fn in [("==", lambda x, y: x == y), ("!=", lambda x, y: x != y), ("<", lambda x, y: x < y),
                                     ("<=", lambda x, y: x <= y), (">", lambda x, y: x > y), (">=", lambda x, y: x >= y)]:
                        out.append((name, self.attempt(lambda: fn(A, B))))
                        out.append((name + "i", self.attempt(lambda: fn(A, r2.choice(ints)))))
                        out.append((name + "f", self.attempt(lambda: fn(A, r2.choice(floats)))))
                        out.append((name + "s", self.attempt(lambda: fn(A, "x"))))
                elif kind == "pow":
                    for ex in [0, 1, 2, 3, -1, -2, 5, 10, 17, -7, 100]:
                        out.append(("p%d" % ex, self.attempt(lambda: norm(A ** ex))))
                        out.append(("pd%d" % ex, self.attempt(lambda: norm(A ** mod.Decimal(ex)))))
                elif kind == "ctor":
                    for v in [a, b, " " + a + " ", a + "x", "", " ", "+", ".", "e5", "1e", "1_0", "1__0", "_1", "1_", "\u0661\u0662",
                              "1.2.3", "+-1", "1e+", "--1"]:
                        out.append(("s" + v, self.attempt(lambda: norm(mod.Decimal(v)))))
                    for v in [0, 5, -5, True, 2 ** 100, 1.5, -0.0, 0.1, 1e300, 5e-324, float("inf"), float("nan"), None, [],
                              (1,), [0, (1, 2), -1], (1, (0,), "F"), (0, (1, 2, 3), "n"), (2, (1,), 0), (0, (10,), 0),
                              (0, (1,), 1.5), (0, 5, 5), b"1"]:
                        out.append(("v" + repr(v), self.attempt(lambda: norm(mod.Decimal(v)))))
                elif kind == "conv":
                    for v in [1, 2.5, "x", None, True, [1], 2 ** 65]:
                        for name, fn in [("+", lambda x, y: x + y), ("-", lambda x, y: x - y), ("*", lambda x, y: x * y),
                                         ("/", lambda x, y: x / y), ("r+", lambda x, y: y + x), ("r-", lambda x, y: y - x),
                                         ("r*", lambda x, y: y * x), ("r/", lambda x, y: y / x), ("//", lambda x, y: x // y),
                                         ("%", lambda x, y: x % y), ("r//", lambda x, y: y // x), ("r%", lambda x, y: y % x),
                                         ("divmod", divmod), ("rdivmod", lambda x, y: divmod(y, x))]:
                            out.append((name + repr(v), self.attempt(lambda: norm(fn(A, v)))))
                else:
                    out.append(("sum", self.attempt(lambda: norm(sum([A, B, A])))))
                    out.append(("sum0", self.attempt(lambda: norm(sum([A, B], mod.Decimal(0))))))
                    out.append(("max", self.attempt(lambda: norm(max(A, B)))))
                    out.append(("sorted", self.attempt(lambda: norm(sorted([A, B, A])))))
                    out.append(("create", self.attempt(lambda: norm(mod.Context(prec=5).create_decimal(a)))))
                return out

            setctx(decimal, prec, rounding, emin, emax, caps)
            want = case(decimal)
            setctx(P, prec, rounding, emin, emax, caps)
            got = case(P)
            self.assertEqual(len(want), len(got))
            for x, y in zip(want, got):
                checked += 1
                self.assertEqual(y, x, "%s ctx=%r a=%r b=%r op=%r" % (kind, (prec, rounding, emin, emax, caps), a, b, x[0]))
        self.assertGreater(checked, 3000)
        setctx(decimal, 28, "ROUND_HALF_EVEN", -999999, 999999, 1)
        setctx(P, 28, "ROUND_HALF_EVEN", -999999, 999999, 1)

    def test_context_checks(self):
        import decimal
        import prelude_decimal as P
        for name, value in [("prec", 0), ("prec", 10 ** 19), ("prec", "x"), ("prec", 1.5), ("prec", 2 ** 63), ("Emax", -2 ** 64), ("capitals", True), ("clamp", True), ("Emax", -1), ("Emin", 1),
                            ("capitals", 2), ("rounding", "ROUND_NOPE"), ("rounding", 5), ("clamp", 7)]:
            want = self.attempt(lambda: setattr(decimal.Context(), name, value))
            got = self.attempt(lambda: [P._ail_dec_set(P.Context(), name, value), None][1])
            self.assertEqual(got[:2], want[:2], (name, value))
            if want[0] == "err":
                self.assertEqual(got[2], want[2], (name, value))
        for bad in (5, "bad", b"ROUND_UP"):
            for call in (lambda M, r: M.Decimal("1.55").quantize(M.Decimal("0.1"), rounding=r),
                         lambda M, r: M.Decimal("1.55").to_integral_value(r),
                         lambda M, r: M.Decimal("1.55").to_integral_exact(r)):
                self.assertEqual(self.attempt(lambda: repr(call(P, bad))), self.attempt(lambda: repr(call(decimal, bad))), bad)
        for bad in (5, "bad", b"ROUND_UP"):
            for call in (lambda M, r: M.Decimal("1.55").quantize(M.Decimal("0.1"), rounding=r),
                         lambda M, r: M.Decimal("1.55").to_integral_value(r),
                         lambda M, r: M.Decimal("1.55").to_integral_exact(r)):
                self.assertEqual(self.attempt(lambda: repr(call(P, bad))), self.attempt(lambda: repr(call(decimal, bad))), bad)


class CompiledPrograms(unittest.TestCase):
    def check(self, name, text, inputs, **env):
        with tempfile.TemporaryDirectory() as directory:
            built, source, exe = compile_python(directory, text, "p_" + name, **env)
            self.assertEqual(built.returncode, 0, "%s %r\n%s%s" % (name, env, built.stdout, built.stderr))
            for k, stdin in enumerate(inputs):
                want = subprocess.run([sys.executable, "-X", "utf8", str(source)], input=stdin.encode(), capture_output=True,
                                      timeout=300)
                got = subprocess.run([str(exe)], input=stdin.encode(), capture_output=True, timeout=300)
                self.assertEqual(got.returncode, want.returncode, "%s input %d: %s" % (name, k, got.stderr[-300:]))
                if got.stdout != want.stdout:
                    a, b = got.stdout.decode().splitlines(), want.stdout.decode().splitlines()
                    for n, (x, y) in enumerate(zip(a, b)):
                        if x != y:
                            self.fail("%s input %d %r line %d:\n  compiled: %r\n  CPython:  %r" % (name, k, env, n + 1, x, y))
                    self.fail("%s input %d: %d lines against %d" % (name, k, len(a), len(b)))

    def test_money_program_matches_cpython(self):
        for env in ({}, {"AIL_UNIFIED_FORCE": "1"}):
            with self.subTest(env=env):
                self.check("money", MONEY, money_inputs(), **env)

    def test_math_functions_on_decimals_match_cpython(self):
        for env in ({}, {"AIL_UNIFIED_FORCE": "1"}):
            with self.subTest(env=env):
                self.check("maths", MATHS, [""], **env)

    def test_edge_inputs_match_cpython(self):
        for env in ({}, {"AIL_UNIFIED_FORCE": "1"}):
            with self.subTest(env=env):
                self.check("edges", EDGES, [EDGE_LINES], **env)


DATE_KEYS = r"""
from datetime import date, timedelta
from decimal import Decimal

d = {}
d.setdefault(date(2024, 1, 15), []).append(Decimal("5.5"))
d.setdefault(date(2024, 1, 29), []).append(Decimal("7"))
day = date(2024, 1, 1)
hits = Decimal(0)
while day <= date(2024, 2, 1):
    for x in d.get(day, []):
        hits += x
    day += timedelta(days=1)
print(hits)
e = {}
for off in range(0, 40, 14):
    e.setdefault(date(2024, 1, 1) + timedelta(days=off), []).append(off)
print(len(e), date(2024, 1, 1) + timedelta(days=14) in e, e[date(2024, 1, 15)], d.get(date(2024, 3, 1)))
"""


class DateKeys(unittest.TestCase):
    """A date used as a dict key finds the entry stored under an equal date (the generated class had no __eq__ / __hash__)."""

    def test_dict_keyed_by_date(self):
        for env in ({}, {"AIL_UNIFIED_FORCE": "1"}):
            with self.subTest(env=env), tempfile.TemporaryDirectory() as directory:
                built, source, exe = compile_python(directory, DATE_KEYS, "datekeys", **env)
                self.assertEqual(built.returncode, 0, "%r\n%s%s" % (env, built.stdout, built.stderr))
                want = subprocess.run([sys.executable, str(source)], capture_output=True)
                got = subprocess.run([str(exe)], capture_output=True)
                self.assertEqual((got.returncode, got.stdout), (want.returncode, want.stdout))


class Refusals(unittest.TestCase):
    CASES = {
        "traps": ("from decimal import Decimal, getcontext\nimport decimal\n"
                  "getcontext().traps[decimal.InvalidOperation] = False\nprint(Decimal(1))\n", "decimal.Context.traps is not supported"),
        "flags": ("from decimal import Decimal, getcontext\nprint(getcontext().flags)\n", "decimal.Context.flags is not supported"),
        "basic": ("from decimal import Decimal, BasicContext\nprint(Decimal(1))\n", "decimal.BasicContext is not supported"),
        "ln": ("from decimal import Decimal\nprint(Decimal(2).ln())\n", "decimal.Decimal.ln is not supported"),
        "as_tuple": ("from decimal import Decimal\nprint(Decimal('1.5').as_tuple())\n", "decimal.Decimal.as_tuple is not supported"),
        "fma": ("from decimal import Decimal\nprint(Decimal(2).fma(3, 4))\n", "decimal.Decimal.fma is not supported"),
        "fraction exponent": ("from decimal import Decimal\nprint(Decimal(4) ** Decimal('0.5'))\n", "non-integer exponent is not supported"),
        "pow3": ("from decimal import Decimal\nprint(pow(Decimal(4), 2, 5))\n", "three-argument pow is not supported"),
        "ctx traps keyword": ("from decimal import Decimal, Context\nc = Context(prec=5, traps=[])\nprint(Decimal(1))\n",
                              "decimal.Context(traps=...) is not supported"),
        "clamp": ("from decimal import Decimal, getcontext\ngetcontext().clamp = 1\nprint(Decimal(1))\n",
                  "decimal.Context.clamp is not supported"),
        "name clash": ("from decimal import Decimal\nclass Context:\n    pass\nprint(Decimal(1))\n", "binds the name Context itself"),
        "module as value": ("import decimal\nm = decimal\nprint(m.Decimal(1))\n", "decimal used as a value"),
        "other attribute": ("import decimal\nprint(decimal.HAVE_THREADS)\n", "decimal.HAVE_THREADS is not supported"),
        "star": ("from decimal import *\nprint(Decimal(1))\n", "from decimal import *"),
        "subclass": ("from decimal import Decimal\nclass Money(Decimal):\n    pass\nprint(Money('1.5'))\n",
                     "a subclass of Decimal is not supported"),
        "statistics": ("import statistics\nfrom decimal import Decimal\nprint(statistics.mean([Decimal(1), Decimal(2)]))\n",
                       "decimal with statistics.mean is not supported"),
    }

    def test_refusals_name_the_use(self):
        for name, (text, wanted) in self.CASES.items():
            with self.subTest(name):
                with tempfile.TemporaryDirectory() as directory:
                    built, _, exe = compile_python(directory, text, "refused")
                    shown = built.stdout + built.stderr
                    self.assertNotEqual(built.returncode, 0, "compiled but should be refused: " + name)
                    self.assertIn(wanted, shown)
                    self.assertFalse(exe.exists())
        with tempfile.TemporaryDirectory() as directory:
            built, _, _ = compile_python(directory, self.CASES["ln"][0], "refused")
            self.assertRegex(built.stdout + built.stderr, r"refused\.py:2: decimal\.Decimal\.ln is not supported; write instead: ")


class UnchangedPrograms(unittest.TestCase):
    def test_programs_without_decimal_keep_their_text(self):
        import stdlib5
        for text in ["# decimal and Decimal only in a comment\nprint(1)\n", "s = 'from decimal import Decimal'\nprint(s)\n",
                     "import math\nprint(math.floor(2.5))\n"]:
            notes = []
            self.assertEqual(stdlib5.rewrite_text(text, notes), text)
            self.assertEqual(notes, [])


if __name__ == "__main__":
    unittest.main()
