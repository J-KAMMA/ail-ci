"""Library batch 1: small, high-use standard-library pieces, each compared with CPython.

Every program below is ordinary Python. CPython runs it as the oracle, the compiled program (the
Python syntax, AIL_NO_GENERAL=1 so the typed path must take it) prints the same bytes, or the
spelling is refused by name -- there is no third outcome where the numbers differ.

* math: sin cos tan asin acos atan atan2 sinh cosh tanh asinh acosh atanh exp exp2 expm1 log (one or
  two arguments) log1p log2 log10 cbrt pow fmod hypot copysign fabs degrees radians trunc factorial
  isnan isinf isfinite. The libm ones call the same glibc routine CPython does, with CPython's
  domain / range errors (ValueError "math domain error", OverflowError "math range error"); math.pow
  and math.hypot carry CPython's own logic (hypot is not libm's hypot). A math name that is not
  built is refused by name.
* f-strings, str.format and `%`: the whole CPython format-spec grammar for int, float and str
  fields (fill, align including `=`, sign, `#`, `0`, width, `,` / `_` grouping, precision, types
  d x X o b e E f F g G %), `!r` / `!s`; a type-less float is the repr (it was `%f`), `{x:>05d}`
  puts the zeros left of the sign as CPython does. The few combinations CPython groups oddly or
  the runtime does not build are refused by name.
* int(s, base) (2..36 and 0, CPython's prefixes, underscores and ValueError message), the three-
  argument pow (exact for every int64, modular inverse for a negative exponent, CPython's
  ValueErrors), map / filter / zip walked by a `for` or consumed by list() / sorted() / set() /
  join() / any() / all() / a leading sum() / min() / max(), max(X, key=K) / min(X, key=K) as a
  statement's value, dict comprehensions (iterlower.py). Shapes that cannot be proved to be
  sequences (zip over a dict) are left to the old refusals.
* sys.maxsize, sys.stderr.write / flush (print(file=sys.stderr) already worked), `with open(path,
  "w"/"wb"/"a"/"ab") as f` with f.write statements, time.perf_counter / monotonic (and _ns),
  os.cpu_count, the string constants, operator.add/mul/... and itemgetter(k) as a key. time.time()
  (wall clock) is refused by name.
"""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent

CATCH = """        try:
            print({expr})
        except ValueError:
            print("VE")
        except OverflowError:
            print("OE")
        except ZeroDivisionError:
            print("ZE")
"""

MATH_ONE = ("sin cos tan asin acos atan sinh cosh tanh asinh acosh atanh exp exp2 expm1 log log1p log2 "
            "log10 cbrt").split()
MATH_TWO = ("atan2 copysign hypot pow fmod").split()
MATH_VALUES = ["0.0", "-0.0", "0.5", "-0.5", "1.0", "-1.0", "2.0", "3.0", "10.0", "-7.25", "1e-9", "123.456",
               "709.5", "709.8", "-745.2", "-800.0", "1e300", "-1e300", "5e-324", "1e-310", "math.inf",
               "-math.inf", "math.nan", "math.pi", "0.1"]


def math_program():
    lines = ["import math", "", "", "def main() -> int:", "    xs = [%s]" % ", ".join(MATH_VALUES),
             "    for a in xs:", "        print(a)"]
    for name in MATH_ONE:
        lines.append(CATCH.format(expr="math.%s(a)" % name).rstrip("\n"))
    lines += ["        print(math.fabs(a), math.degrees(a), math.radians(a), math.isnan(a), math.isinf(a), "
              "math.isfinite(a))", "        for b in xs:"]
    for name in MATH_TWO:
        lines.append(CATCH.format(expr="math.%s(a, b)" % name).replace("\n        ", "\n            ")
                     .replace("        try", "            try", 1).rstrip("\n"))
    lines.append(CATCH.format(expr="math.log(a, b)").replace("\n        ", "\n            ")
                 .replace("        try", "            try", 1).rstrip("\n"))
    lines += ["    return 0", "", "", "main()", ""]
    return "\n".join(lines)


FMT_INTS = ["0", "7", "-7", "255", "-255", "1234567", "-1234567", "9223372036854775807", "-9223372036854775807"]
FMT_FLOATS = ["0.0", "-0.0", "3.14159", "-2.5", "1234567.891", "0.000123", "1e16", "-1e-7", "0.5", "2.5", "1e300",
              'float("inf")', 'float("-inf")', 'float("nan")']
FMT_STRS = ['"abc"', '""', '"héllo"', '"it\'s"']


def format_fields():
    """(value, spec) pairs drawn from the whole grammar, keeping only what CPython accepts and what the
    compiler documents as built (grouping with zero padding and a type-less `.0` float are refused)."""
    import random
    import re
    rng = random.Random(3)
    pattern = re.compile(r"^(?:(.)?([<>^=]))?([+\- ])?(#)?(0)?(\d+)?([,_])?(?:\.(\d+))?(.)?$")

    def built(value, spec):
        m = pattern.match(spec)
        if not m:
            return False
        fill, align, sign, alt, zero, width, group, prec, typ = m.groups()
        if group and ("0" if zero and not fill else fill or " ") == "0" \
                and (align or ("=" if zero and not fill else "")) == "=":
            return False
        if type(eval(value)) is float and not typ and (alt or prec == "0"):
            return False
        try:
            format(eval(value), spec)
        except (ValueError, TypeError, OverflowError):
            return False
        return True

    def specs(fills, aligns, signs, widths, groups, precs, types):
        out = []
        for fill in fills:
            for align in aligns:
                if fill and not align:
                    continue
                for sign in signs:
                    for alt in ["", "#"]:
                        for zero in ["", "0"]:
                            for width in widths:
                                for group in groups:
                                    for prec in precs:
                                        for typ in types:
                                            out.append(fill + align + sign + alt + zero + width + group + prec + typ)
        rng.shuffle(out)
        return out

    fields = []
    for values, pool, limit in (
            (FMT_INTS, specs(["", "*", "0", "é"], ["", "<", ">", "^", "="], ["", "+", " "], ["", "12"],
                             ["", ",", "_"], [""], ["", "d", "x", "X", "o", "b", "f", "e", "g", "%"]), 260),
            (FMT_FLOATS, specs(["", "*"], ["", "<", ">", "^", "="], ["", "+", " "], ["", "14"], ["", ",", "_"],
                               ["", ".2", ".10"], ["", "f", "e", "E", "g", "G", "F", "%"]), 260),
            (FMT_STRS, [f + a + w + p for f in ["", "*", "é"] for a in ["", "<", ">", "^"]
                        for w in ["", "3", "10"] for p in ["", ".2", ".0"] if a or not f], 40)):
        taken = 0
        for spec in pool:
            value = rng.choice(values)
            if built(value, spec):
                fields.append((value, spec))
                taken += 1
                if taken >= limit:
                    break
    return fields


def format_program():
    lines = ["def main() -> int:"]
    for index, (value, spec) in enumerate(format_fields()):
        lines.append('    print(f"[{%s:%s}]")' % (value, spec))
        if index % 7 == 0:
            lines.append('    print("[{:%s}]".format(%s))' % (spec, value))
    for value in FMT_INTS[:3] + FMT_STRS[:3] + FMT_FLOATS[:3]:
        lines.append('    print(f"{%s!r} {%s!r:>12} {%s!s}", "{!r}".format(%s))' % (value, value, value, value))
    lines += ["    return 0", "", "main()", ""]
    return "\n".join(lines)


MATH_MISC = '''import math
from math import sin, pi, hypot


def main() -> int:
    print(sin(1), math.exp(1), math.log(10), math.log(8, 2), math.log2(8), math.log10(1000), math.log(2.0, 10))
    print(math.pow(2, 10), math.hypot(3, 4), hypot(5, 12), math.fmod(7.5, 2), math.fmod(-7.5, 2))
    print(math.trunc(-2.7), math.trunc(7), math.trunc(2.5), math.factorial(10), math.factorial(0))
    print(math.fabs(-0.0), math.copysign(3, -0.0), math.atan2(-0.0, -1.0), math.cbrt(-8))
    print(math.degrees(pi), math.radians(180), math.isnan(math.nan), math.isinf(-math.inf), math.isfinite(1))
    try:
        print(math.factorial(-1))
    except ValueError:
        print("neg")
    try:
        print(math.log(8.0, 1.0))
    except ZeroDivisionError:
        print("zero")
    return 0


main()
'''


ITERATORS = r'''def double(x: int) -> int:
    return x * 2


def pick(t: int) -> int:
    return -abs(t - 3)


def main() -> int:
    tokens = ["1", "2", "x", "4"]
    total = 0
    try:
        for v in map(int, tokens):
            print("got", v)
            total += v
    except ValueError:
        print("stopped", total)
    nums = [3, 0, 5, 0, 7]
    for w in filter(None, nums):
        print("nz", w)
    for w in filter(lambda n: n % 2 == 1, nums):
        print("odd", w)
    print(w)
    for k in map(lambda n: n * n + 1, nums):
        print(k)
    for k in map(double, nums):
        print(k)
    a = [1, 2, 3]
    b = [10, 20, 30, 40, 50]
    c = "xyz"
    for p, q in zip(a, b):
        print(p, q)
        if len(a) < 6:
            a.append(p + 100)
    for p, q, r in zip(a, b, c):
        print(p, q, r)
    for p, q in zip(a, a[1:]):
        print(q - p)
    for p, q in zip(range(5), b):
        print(p, q)
    for p, q in zip(range(2, 6), range(10)):
        print(p, q)
    for ch, num in zip("abc", [1, 2, 3, 4]):
        print(ch, num)
    for u, v2 in zip([], b):
        print("never")
    words = ["pear", "fig", "banana", "kiwi", "fig"]
    best = max(words, key=len)
    least = min(words, key=len)
    print(best, least)
    big = max(nums, key=pick)
    small = min(nums, key=lambda n: (n - 4) * (n - 4))
    print(big, small)
    first = max(range(3, 9), key=lambda i: i % 4)
    print(first)
    ee: list[int] = []
    try:
        e = max(ee, key=abs)
    except ValueError:
        print("empty")
    ys = list(map(int, ["5", "6"]))
    zs = sorted(map(abs, [-3, 2, -1]))
    print(len(ys), ys[0], zs[0], zs[2])
    t = sum(map(int, tokens[0:2]))
    m = max(map(len, words))
    n = min(map(len, words))
    s2 = sum(map(len, words)) + 1
    print(t, m, n, s2)
    print(any(map(int, ["0", "1", "x"])), all(map(int, ["1", "0", "x"])))
    print(",".join(map(str, nums)))
    sq = {n: n * n for n in nums if n > 0}
    print(len(sq), sq[5], sq[7])
    idx = {ch: len(ch) + 1 for ch in "hello"}
    print(len(idx), idx["l"], idx["o"])
    pairs = {i + j: i * j for i in range(3) for j in range(3) if i != j}
    print(len(pairs), pairs[3], pairs[1])
    n = 99
    dd = {n: n for n in range(2)}
    print(n, len(dd))
    print(max(nums, key=lambda v: -v))
    total2 = 2 * max(nums, key=abs) + 1
    if min(nums, key=lambda v: abs(v - 6)) == 5:
        print("five", total2)
    elif sum(map(abs, nums)) > 100:
        print("big")
    else:
        print("other", sum(map(abs, nums)))
    return 0

main()
'''

INT_POW_FUZZ = r'''import sys

def main() -> int:
    for line in sys.stdin:
        parts = line.rstrip("\n").split("\t")
        if parts[0] == "p":
            a = int(parts[1])
            b = int(parts[2])
            m = int(parts[3])
            try:
                print(pow(a, b, m))
            except ValueError:
                print("VE")
        else:
            base = int(parts[1])
            s = parts[2]
            try:
                print(int(s, base))
            except ValueError:
                print("VE")
    return 0

main()
'''

INT_POW_EDGES = r'''def main() -> int:
    for s in ["ff", " FF ", "-0x1f", "0x1F", "z", "", "_1", "1_000", "1__0", "0b101", "+7", "zz", "  12  "]:
        for b in [16, 36, 2, 0, 10, 8]:
            try:
                print(s, b, int(s, b))
            except ValueError:
                print(s, b, "VE")
    print(int("777", base=8), pow(3, 4, 5), pow(2, -1, 7), pow(-2, 5, 7), pow(5, 0, -5), pow(3, 100, -17), pow(0, 0, 1))
    try:
        print(pow(2, -1, 4))
    except ValueError:
        print("noinv")
    try:
        print(pow(2, 3, 0))
    except ValueError:
        print("zero")
    print(pow(123456789, 987654321, 1000000007), pow(3, -5, 1000000007), pow(2, 62, 9223372036854775807))
    print(pow(-7, -1, 13), pow(-7, -3, -13), pow(10, 18, 998244353))
    return 0

main()
'''


SMALL_MODULES = r'''import os
import string
import time
import operator
from operator import itemgetter


def main() -> int:
    t0 = time.perf_counter()
    n0 = time.perf_counter_ns()
    c = os.cpu_count()
    print(c)
    print(string.ascii_lowercase, string.ascii_uppercase, string.digits)
    print(string.ascii_letters, string.punctuation, string.hexdigits, string.octdigits)
    print(len(string.whitespace), len(string.printable))
    for ch in string.digits:
        print(ch, end="")
    print()
    print(operator.add(1, 2), operator.mul(3, 4), operator.sub(9, 4), operator.truediv(1, 4), operator.floordiv(9, 2))
    print(operator.lt(1, 2), operator.eq(3, 3), operator.neg(5), operator.not_(0), operator.mod(7, 3), operator.pow(2, 8))
    xs = [3, 1, 2]
    print(operator.getitem(xs, 1))
    t1 = time.perf_counter()
    n1 = time.perf_counter_ns()
    print(t1 >= t0, n1 >= n0, t1 - t0 < 5.0, time.monotonic() >= t1)
    return 0

main()
'''

WRITE_OPEN = r'''import sys

def main() -> int:
    path = sys.argv[1]
    with open(path, "w") as f:
        f.write("hello\n")
        for i in range(3):
            f.write(f"line {i}\n")
        f.write("héllo ü\n")
    with open(path) as g:
        text = g.read()
    print(len(text))
    print(text)
    with open(path, "a") as f:
        f.write("more\n")
    with open(path, "rb") as g:
        data = g.read()
    print(len(data))
    out = sys.argv[1] + ".bin"
    with open(out, "wb") as f:
        f.write(b"\x00\x01abc")
        f.write(data[0:3])
    with open(out, "rb") as g:
        raw = g.read()
    print(len(raw), raw[0], raw[1], raw[2])
    with open(path, "w", encoding="utf-8") as f:
        pass
    with open(path) as g:
        print(len(g.read()))
    try:
        with open(path, "w") as f:
            f.write("partial")
            n = int("x")
            f.write("never")
    except ValueError:
        print("caught")
    with open(path) as g:
        print(g.read())
    return 0

main()
'''

SYS_BITS = r'''import sys

def main() -> int:
    print("to-stdout")
    sys.stderr.write("err2\n")
    n = 3
    sys.stderr.write(f"n={n}\n")
    sys.stderr.flush()
    print(sys.maxsize, sys.maxsize - 1, -sys.maxsize)
    big = sys.maxsize
    best = big
    for v in [5, 2, 9]:
        if v < best:
            best = v
    print(best)
    return 0

main()
'''


def int_pow_input():
    import random
    rng = random.Random(5)

    def big():
        k = rng.random()
        if k < 0.3:
            return rng.randint(-20, 20)
        if k < 0.6:
            return rng.randint(-10 ** 9, 10 ** 9)
        return rng.randint(-2 ** 63 + 1, 2 ** 63 - 1)

    lines = []
    for _ in range(3000):
        exp = rng.choice([rng.randint(-30, 30), rng.randint(0, 10 ** 9), rng.randint(-10 ** 6, 10 ** 6)])
        lines.append("p\t%d\t%d\t%d" % (big(), exp, big() or 7))
    alphabet = "0123456789abcdefghxXoObBzZ_+- "
    while len(lines) < 7000:
        text = "".join(rng.choice(alphabet) for _ in range(rng.randint(0, 9)))
        if rng.random() < 0.3:
            text = rng.choice(["0x", "0b", "0o", "", "-", "+", "- ", "0X"]) + text
        base = rng.choice([0, 0, 2, 8, 10, 16, 36, rng.randint(2, 36)])
        try:
            if not -2 ** 63 <= int(text, base) < 2 ** 63:
                continue
        except ValueError:
            pass
        lines.append("i\t%d\t%s" % (base, text))
    return ("\n".join(lines) + "\n").encode()


def compile_python(directory, text, name):
    source, exe = Path(directory, name + ".ail"), Path(directory, name)
    source.write_text(text, encoding="utf-8")
    built = subprocess.run([sys.executable, "-B", str(ROOT / "ail_chatgpt.py"), "compile", source.name,
                            "--syntax", "python", "-o", exe.name], cwd=directory, capture_output=True,
                           text=True, timeout=600, env=dict(os.environ, AIL_NO_GENERAL="1"))
    return built, source, exe


class Batch1Tests(unittest.TestCase):
    def same_as_cpython(self, text, name, stdin=b"", args=(), stderr=False):
        with tempfile.TemporaryDirectory() as directory:
            built, source, exe = compile_python(directory, text, name)
            self.assertEqual(built.returncode, 0, built.stdout + built.stderr)
            argv = [str(Path(directory, arg[1:])) if arg.startswith("@") else arg for arg in args]
            ran = subprocess.run([str(exe), *argv], input=stdin, capture_output=True, timeout=120)
            expected = subprocess.run([sys.executable, str(source), *argv], input=stdin, capture_output=True, timeout=120)
            self.assertEqual(expected.returncode, 0, expected.stderr)
            self.assertEqual((ran.returncode, ran.stdout), (0, expected.stdout), ran.stderr)
            if stderr:
                self.assertEqual(ran.stderr, expected.stderr)

    def refused(self, text, wanted, name="prog"):
        with tempfile.TemporaryDirectory() as directory:
            built, _, exe = compile_python(directory, text, name)
            self.assertEqual(built.returncode, 3, built.stdout + built.stderr)
            self.assertIn(wanted, built.stderr)
            self.assertFalse(exe.exists())

    def test_math_libm_functions_match_cpython_bits_and_errors(self):
        self.same_as_cpython(math_program(), "math_grid")

    def test_math_spellings(self):
        self.same_as_cpython(MATH_MISC, "math_misc")

    def test_math_not_built_is_named(self):
        text = "import math\n\n\ndef main():\n    print(math.erf(0.5))\n\n\nmain()\n"
        self.refused(text, "math.erf() with these arguments is not built")
        with tempfile.TemporaryDirectory() as directory:
            built, _, _ = compile_python(directory, text, "prog")
            self.assertNotIn("read before it is assigned", built.stderr)

    def test_format_specs_match_cpython(self):
        self.same_as_cpython(format_program(), "format_grid")

    def test_format_spec_refusals_are_named(self):
        for value, spec, wanted in (("7", "n", "the type 'n'"), ("7", "010,", "grouping"),
                                    ("2.5", ".0", "precision 0"), ("2.5", "z.2f", "'z' option")):
            with self.subTest(spec=spec):
                self.refused('def main():\n    print(f"{%s:%s}")\n\n\nmain()\n' % (value, spec), wanted)

    def test_iterator_spellings_match_cpython(self):
        self.same_as_cpython(ITERATORS, "iterators")

    def test_int_with_base_and_three_argument_pow(self):
        self.same_as_cpython(INT_POW_EDGES, "int_pow_edges")
        self.same_as_cpython(INT_POW_FUZZ, "int_pow_fuzz", int_pow_input())

    def test_unlowered_iterator_shapes_are_still_refused(self):
        # an iterable that is not known to be a sequence is not indexed (a dict's keys are not 0..n-1)
        self.refused("def main():\n    d = {1: 2, 3: 4}\n    e = {5: 6, 7: 8}\n"
                     "    for a, b in zip(d, e):\n        print(a, b)\n\n\nmain()\n", "tuple target")
        # (max(d, key=...) over a dict held in a variable is built since library batch 4; another dict's
        # .get is not a key function it knows)
        self.refused("def main():\n    d = {1: 2, 3: 4}\n    e = {5: 6}\n    k = max(d, key=e.get)\n    print(k)\n\n\nmain()\n",
                     "gives None for a missing key")

    def test_sys_maxsize_and_stderr(self):
        self.same_as_cpython(SYS_BITS, "sys_bits", stderr=True)

    def test_time_string_os_operator(self):
        self.same_as_cpython(SMALL_MODULES, "small_modules")

    def test_with_open_write_modes(self):
        self.same_as_cpython(WRITE_OPEN, "write_open", args=("@out.txt",))

    def test_unbuilt_clock_and_file_shapes_are_named(self):
        self.refused("import time\n\n\ndef main():\n    print(time.time() > 0.0)\n\n\nmain()\n",
                     "time.time() with these arguments is not built")
        self.refused("def main():\n    m = 'w'\n    with open('x', m) as f:\n        f.write('a')\n    print(1)\n\n\nmain()\n",
                     "mode that is not a string literal")


if __name__ == "__main__":
    unittest.main()
