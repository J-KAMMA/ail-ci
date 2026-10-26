"""Big integers (docs/design/BIGINT.md), checked against CPython 3.12 with fixed seeds.

Three layers:

* `CoreLimbs`   -- the C core (`bigint_core.CORE`) built alone as a shared library and driven through ctypes:
                   add, sub, mul (schoolbook and Karatsuba), Knuth division, shifts, decimal text, float rounding.
* `ExactPrograms` -- generated programs (operands 1..300 digits, both signs, every operator) compiled with the
                   general path (unboxed ints off: every int exact) and compared line by line with CPython.
* `DefaultBuild` -- programs through the default build: a function that is likely to need a big int (bigcap) takes the
                   general path, an unmarked one stays typed int64 with the loud "integer overflow" stop; literals beyond int64.
* `MarkRules`   -- which functions bigcap marks.

A program run is one build (about 5 s) however many checks it prints: the operands are data, the operators a loop.
"""
import ctypes
import os
import random
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent
PKG = ROOT / "python" / "pkg-v12"
if str(PKG) not in sys.path:
    sys.path.insert(0, str(PKG))

CC = shutil.which("cc") or shutil.which("gcc") or shutil.which("clang")


def rand_int(rng, max_digits=300):
    """A random int of 1..max_digits digits, either sign, with the edge sizes over-represented."""
    kind = rng.random()
    if kind < 0.15:
        v = rng.choice([0, 1, -1, 2, 10, 2 ** 31, 2 ** 32, 2 ** 32 - 1, 2 ** 53, 2 ** 53 + 1, 2 ** 63 - 1, 2 ** 63, 2 ** 64,
                        2 ** 64 - 1, 2 ** 64 + 1, 10 ** 18, 10 ** 19, 2 ** 100, 2 ** 127, 2 ** 128 - 1, 2 ** 1024 - 1, 2 ** 1024])
        return v * rng.choice([1, -1])
    if kind < 0.3:
        v = rng.randrange(-2 ** 63 - 5, 2 ** 63 + 5)
        return v
    digits = rng.randint(1, max_digits)
    v = rng.randrange(10 ** (digits - 1), 10 ** digits) if digits > 1 else rng.randrange(0, 10)
    if rng.random() < 0.15:
        v = (1 << rng.randint(1, 900)) + rng.choice([-1, 0, 1])      # powers of two and their neighbours
    return -v if rng.random() < 0.5 else v


# ---------------------------------------------------------------------------------------------------- the C core
class CoreLimbs(unittest.TestCase):
    def tearDown(self):
        sys.set_int_max_str_digits(4300)

    @classmethod
    def setUpClass(cls):
        if not CC:
            raise unittest.SkipTest("no C compiler")
        from bigint_core import CORE
        cls.tmp = tempfile.TemporaryDirectory(prefix="ail-bn-")
        d = Path(cls.tmp.name)
        (d / "t.c").write_text(
            "#include <stdint.h>\n#include <stdlib.h>\n#include <string.h>\n#include <stdio.h>\n#include <math.h>\n"
            "static void ail_die(const char *w) { fprintf(stderr, \"%s\\n\", w); exit(9); }\n" + CORE + r'''
size_t t_add(ail_limb *o, const ail_limb *a, size_t na, const ail_limb *b, size_t nb) { return ail_bn_add(o, a, na, b, nb); }
size_t t_sub(ail_limb *o, const ail_limb *a, size_t na, const ail_limb *b, size_t nb) { return ail_bn_sub(o, a, na, b, nb); }
size_t t_mul(ail_limb *o, const ail_limb *a, size_t na, const ail_limb *b, size_t nb) { return ail_bn_mul(o, a, na, b, nb); }
void t_div(ail_limb *q, size_t *qn, ail_limb *r, size_t *rn, const ail_limb *a, size_t na, const ail_limb *b, size_t nb) { ail_bn_divmod(q, qn, r, rn, a, na, b, nb); }
size_t t_shl(ail_limb *o, const ail_limb *a, size_t na, uint64_t b) { return ail_bn_shl(o, a, na, b); }
size_t t_shr(ail_limb *o, const ail_limb *a, size_t na, uint64_t b) { return ail_bn_shr(o, a, na, b); }
size_t t_dec(char *b, const ail_limb *a, size_t na) { return ail_bn_to_dec(b, a, na); }
size_t t_fromdec(ail_limb *o, const char *s, size_t n) { return ail_bn_from_dec(o, s, n); }
double t_dbl(const ail_limb *a, size_t na, int neg, int *ovf) { return ail_bn_to_double(a, na, neg, ovf); }
int t_cmp(const ail_limb *a, size_t na, const ail_limb *b, size_t nb) { return ail_bn_cmp(a, na, b, nb); }
''')
        subprocess.run([CC, "-O2", "-shared", "-fPIC", "-w", "-o", str(d / "t.so"), str(d / "t.c"), "-lm"], check=True)
        L = ctypes.CDLL(str(d / "t.so"))
        vp, sz = ctypes.c_void_p, ctypes.c_size_t
        for name in ("t_add", "t_sub", "t_mul"):
            f = getattr(L, name)
            f.argtypes = [vp, vp, sz, vp, sz]
            f.restype = sz
        L.t_div.argtypes = [vp, vp, vp, vp, vp, sz, vp, sz]
        L.t_shl.argtypes = L.t_shr.argtypes = [vp, vp, sz, ctypes.c_uint64]
        L.t_shl.restype = L.t_shr.restype = sz
        L.t_dec.argtypes = [vp, vp, sz]
        L.t_dec.restype = sz
        L.t_fromdec.argtypes = [vp, ctypes.c_char_p, sz]
        L.t_fromdec.restype = sz
        L.t_dbl.argtypes = [vp, sz, ctypes.c_int, vp]
        L.t_dbl.restype = ctypes.c_double
        L.t_cmp.argtypes = [vp, sz, vp, sz]
        cls.L = L

    @staticmethod
    def limbs(x):
        n = (x.bit_length() + 31) // 32
        return (ctypes.c_uint32 * max(n, 1))(*[(x >> (32 * i)) & 0xffffffff for i in range(n)]), n

    @staticmethod
    def val(buf, n):
        return sum(buf[i] << (32 * i) for i in range(n))

    def test_core_operations(self):
        L, u32, sz = self.L, ctypes.c_uint32, ctypes.c_size_t
        sys.set_int_max_str_digits(0)       # the core has no digit limit (the runtime applies CPython's above it); the oracle must not either
        rng = random.Random(20261021)
        checks = 0

        def rnd():
            b = rng.randint(1, rng.choice([1, 31, 32, 33, 64, 65, 500, 1300, 2000, 5000, 20000]))
            x = rng.getrandbits(b)
            if rng.random() < 0.2:
                x |= (1 << b) - 1                                   # a run of ones: carries and borrows
            return x
        for _ in range(4000):
            a, b = rnd(), rnd()
            A, na = self.limbs(a)
            B, nb = self.limbs(b)
            na, nb = (na if a else 0), (nb if b else 0)
            o = (u32 * (na + nb + 3))()
            self.assertEqual(self.val(o, L.t_mul(o, A, na, B, nb)), a * b)
            self.assertEqual(self.val(o, L.t_add(o, A, na, B, nb)), a + b)
            x, y = max(a, b), min(a, b)
            X, nx = self.limbs(x)
            Y, ny = self.limbs(y)
            nx, ny = (nx if x else 0), (ny if y else 0)
            self.assertEqual(self.val(o, L.t_sub(o, X, nx, Y, ny)), x - y)
            self.assertEqual(L.t_cmp(A, na, B, nb), (a > b) - (a < b))
            if b:
                q, r = (u32 * (na + 2))(), (u32 * (nb + 2))()
                qn, rn = sz(), sz()
                L.t_div(q, ctypes.byref(qn), r, ctypes.byref(rn), A, na, B, nb)
                self.assertEqual((self.val(q, qn.value), self.val(r, rn.value)), divmod(a, b), (a, b))
                checks += 1
            s = rng.randint(0, 200)
            o = (u32 * (na + 8))()
            self.assertEqual(self.val(o, L.t_shl(o, A, na, s)), a << s)
            o = (u32 * (na + 8))()
            self.assertEqual(self.val(o, L.t_shr(o, A, na, s)), a >> s)
            if a:
                text = str(a)
                buf = ctypes.create_string_buffer(10 * na + 2)
                nd = L.t_dec(buf, A, na)            # (the buffer is read after the call has filled it)
                self.assertEqual(buf.raw[:nd].decode(), text)
                o = (u32 * (len(text) // 9 + 3))()
                self.assertEqual(self.val(o, L.t_fromdec(o, text.encode(), len(text))), a)
            ovf = ctypes.c_int()
            d = L.t_dbl(A, na, 0, ctypes.byref(ovf))
            try:
                want, want_ovf = float(a), 0
            except OverflowError:
                want, want_ovf = 0.0, 1
            self.assertEqual(ovf.value, want_ovf)
            if not want_ovf:
                self.assertEqual(d, want, a)
            checks += 10
        self.assertGreater(checks, 30000)

    def test_knuth_correction_cases(self):
        """qhat one too large (the add-back step) and divisors with all-ones top limbs."""
        L, u32, sz = self.L, ctypes.c_uint32, ctypes.c_size_t
        rng = random.Random(7)
        for _ in range(20000):
            nb = rng.randint(2, 6)
            na = nb + rng.randint(0, 6)
            b = rng.getrandbits(32 * nb) | (1 << (32 * nb - 1)) if rng.random() < 0.5 else rng.getrandbits(32 * nb) | 1
            if rng.random() < 0.5:
                b |= ((1 << 32) - 1) << (32 * (nb - 1))
            a = rng.getrandbits(32 * na)
            if rng.random() < 0.3:
                a = max(0, b * rng.getrandbits(32 * (na - nb + 1)) + rng.choice([0, -1, 1]))
            A, la = self.limbs(a)
            B, lb = self.limbs(b)
            la = la if a else 0
            q, r = (u32 * (la + 2))(), (u32 * (lb + 2))()
            qn, rn = sz(), sz()
            L.t_div(q, ctypes.byref(qn), r, ctypes.byref(rn), A, la, B, lb)
            self.assertEqual((self.val(q, qn.value), self.val(r, rn.value)), divmod(a, b))


# ------------------------------------------------------------------------------------------------ generated programs
def run_program(text, tmp, name, env_extra=None, build_extra=()):
    """Build `text` with the compiler (python syntax) and run it; returns (CPython result, built result)."""
    src = Path(tmp) / (name + ".py")
    src.write_text(text, encoding="utf-8")
    exe = Path(tmp) / (name + "_exe")
    env = dict(os.environ)
    env.update(env_extra or {})
    env["AIL_NO_CACHE"] = "1"
    env["AIL_QUIET_FALLBACK"] = "1"
    want = subprocess.run([sys.executable, str(src)], capture_output=True, text=True, timeout=300)
    made = subprocess.run([sys.executable, "-B", str(ROOT / "ail_chatgpt.py"), "compile", str(src), "--syntax", "python",
                           "-o", str(exe), *build_extra], capture_output=True, text=True, timeout=900, env=env)
    got = None
    if exe.exists():
        got = subprocess.run([str(exe)], capture_output=True, text=True, timeout=300, env=env)
    return want, made, got


ARITH = '''
A = %(A)r
B = %(B)r
def show(tag, f, a, b):
    try:
        print(tag, f(a, b))
    except Exception as e:
        print(tag, type(e).__name__, e)
def main():
    n = len(A)
    for i in range(n):
        a = int(A[i])
        b = int(B[i])
        s = 0
        print(i, a + b, a - b, a * b, -a, abs(a), a < b, a <= b, a == b, a != b, a > b, a >= b)
        if b != 0:
            print(a // b, a %% b, divmod(a, b))
        else:
            print("zerodiv")
        print(a & b, a | b, a ^ b, ~a, a >> (i %% 70), a << (i %% 70))
        print(str(a), hex(a), oct(b), bin(a))
        print(a.bit_length(), hash(a), hash(b), bool(a), a %% 1000003, a // 1000003, a + 1, a - 1, a * 2, a * -3)
        f = float(b) if abs(b) < 10 ** 300 else 1.5
        print(a < f, a == f, a > f, a + 1.5 if abs(a) < 10 ** 300 else 0.5, f * 2)
        print(sum([a, b, a]), max(a, b), min(a, b), sorted([a, b, 0, -a]))
        print(f"{a:,}", f"{b:_}", f"{a:x}", f"{a:#o}", f"{b:>40}"[:60], "%%d %%x" %% (a, b))
        if i %% 7 == 0:
            print(a ** (i %% 5), pow(a, i %% 9, 1000000007), pow(a, 3, b) if b != 0 else 0)
        if i %% 11 == 0 and abs(a) < 10 ** 120:
            print(a ** 3, (a * a) // (a - 1 if a != 1 else 2))
main()
'''


def arith_program(seed, n):
    rng = random.Random(seed)
    A, B = [], []
    for _ in range(n):
        a = rand_int(rng)
        b = rand_int(rng, rng.choice([5, 20, 100, 300]))
        A.append(str(a))
        B.append(str(b))
    return ARITH % {"A": A, "B": B}


MATH_PROGRAM = '''
import math
A = %(A)r
def main():
    for i in range(len(A)):
        a = int(A[i])
        b = int(A[(i * 7 + 3) %% len(A)])
        print(math.gcd(a, b), math.gcd(b, a), math.lcm(abs(a) %% 10**40, abs(b) %% 10**40))
        print(math.isqrt(abs(a)), math.isqrt(abs(a)) ** 2 <= abs(a))
        print(math.floor(a), math.ceil(a), math.trunc(a), int(float(a)) if abs(a) < 10**300 else 0)
        if a > 0:
            print(math.log(a), math.log2(a), math.log10(a), math.log(a, 7))
        print(round(a, -3), round(a, -25), round(a), a.bit_count(), a.to_bytes(140, "little", signed=True) if abs(a) < 2**1000 else b"")
        print(int.from_bytes(a.to_bytes(140, "big", signed=True), "big", signed=True) == a if abs(a) < 2**1000 else True)
        print(int(str(a)), int(hex(a), 16), int(bin(a), 2), int(oct(a), 8), int(hex(a), 0), int(str(a) + "  ", 10), int(" +" + str(abs(a))))
        print(a / b if b != 0 and abs(a) < 10 ** 300 else 1.0, a / 7)
        print(a // 3.5 if abs(a) < 10 ** 300 else 0, a %% 3.5 if abs(a) < 10 ** 300 else 0)
    print(math.factorial(25), math.factorial(60), math.factorial(500) %% 10**20, math.comb(100, 50), math.comb(1000, 3), math.comb(10**20, 3),
          math.perm(30, 12), math.perm(100, 3), math.perm(10**20, 2), math.prod([2**40, 2**40, 2**40]), math.isqrt(10**80), math.isqrt(10**80 - 1))
    print(len(str(math.factorial(1500))), math.factorial(1500) %% (2**89 - 1), sum(range(10**5)) * 10**14)
main()
'''


def math_program(seed, n):
    rng = random.Random(seed)
    return MATH_PROGRAM % {"A": [str(rand_int(rng, rng.choice([3, 30, 150, 300]))) for _ in range(n)]}


class ExactPrograms(unittest.TestCase):
    """Operators and conversions on the exact general path, line by line against CPython."""
    @classmethod
    def setUpClass(cls):
        if not CC:
            raise unittest.SkipTest("no C compiler")
        cls.tmp = tempfile.TemporaryDirectory(prefix="ail-bigprog-")

    def compare(self, text, name, env=None):
        env = dict({"AIL_UNIFIED_FORCE": "1", "AIL_UNIFIED": "0"}, **(env or {}))
        want, made, got = run_program(text, self.tmp.name, name, env)
        self.assertEqual(made.returncode, 0, made.stderr[-3000:])
        self.assertIsNotNone(got)
        self.assertEqual(want.returncode, 0, want.stderr[-1500:])
        self.assertEqual(got.stderr, "")
        self.assertEqual(got.returncode, 0)
        wl, gl = want.stdout.splitlines(), got.stdout.splitlines()
        self.assertEqual(len(wl), len(gl))
        for k, (w, g) in enumerate(zip(wl, gl)):
            if w != g:
                self.fail("line %d\n  CPython: %s\n  AIL:     %s" % (k, w[:600], g[:600]))
        self.checks = getattr(self, "checks", 0) + sum(len(w.split()) for w in wl)     # each printed value is one differential check
        return len(wl)

    def test_arithmetic_comparison_bitwise_text(self):
        lines = self.compare(arith_program(1, 700), "arith1")
        self.assertGreater(lines, 5000)
        self.assertGreater(self.checks, 20000, "the differential checks of this run (one per printed value)")

    def test_arithmetic_second_seed(self):
        self.compare(arith_program(20261021, 500), "arith2")

    def test_math_conversions(self):
        self.compare(math_program(5, 250), "math1")


# ------------------------------------------------------------------------------------------------ the default build
CASES = ROOT / "bigint_cases"


class DefaultBuild(unittest.TestCase):
    """Programs of bigint_cases/ through the default build (typed first, unified general path otherwise): stdout and the
    exit status are CPython's; stdin (when a .in file exists) is fed to CPython and to the build alike."""
    @classmethod
    def setUpClass(cls):
        if not CC:
            raise unittest.SkipTest("no C compiler")
        cls.tmp = tempfile.TemporaryDirectory(prefix="ail-bigdef-")

    def check(self, name, stdin_pipe=False):
        text = (CASES / (name + ".py")).read_text(encoding="utf-8")
        inp = CASES / (name + ".in")
        data = inp.read_bytes() if inp.exists() else b""
        src = Path(self.tmp.name) / (name + ".py")
        src.write_text(text, encoding="utf-8")
        exe = Path(self.tmp.name) / (name + "_exe")
        env = dict(os.environ, AIL_NO_CACHE="1", AIL_QUIET_FALLBACK="1")
        want = subprocess.run([sys.executable, str(src)], input=data, capture_output=True, timeout=300)
        made = subprocess.run([sys.executable, "-B", str(ROOT / "ail_chatgpt.py"), "compile", str(src), "--syntax", "python",
                               "-o", str(exe)], capture_output=True, text=True, timeout=900, env=env)
        self.assertEqual(made.returncode, 0, made.stdout[-500:] + made.stderr[-3000:])
        got = subprocess.run([str(exe)], input=data, capture_output=True, timeout=300, env=env)
        self.assertEqual(got.stdout.decode(), want.stdout.decode(), name)
        self.assertEqual(got.returncode, want.returncode, name)
        if want.returncode == 0:
            self.assertEqual(got.stderr, want.stderr, name)
        return want, got

    def test_literals_and_containers(self):
        self.check("big_literals")
        self.check("big_containers")

    def test_int_text_limit(self):
        self.check("digit_limit")

    def test_range_and_index(self):
        self.check("big_range")
        self.check("big_index")

    def test_float_conversion_and_zero_division_texts(self):
        self.check("float_overflow")
        self.check("zero_division")

    def test_float_format_overflow(self):
        """`%f`/`%e`/`%g`, format() and f-strings of an int beyond the double range raise CPython's
        OverflowError instead of returning inf or TypeError, through an argument, list item, dict value
        and attribute; a representable int near the top of the range formats its full text."""
        self.check_both("float_format_overflow")

    def test_big_format_precision_and_char(self):
        """High-precision e/E/g/f/% of an int inside the double range keep every requested digit (not a
        300-digit cap), and %c/format(...,'c') of a big int raise CPython's exception and text, through
        an argument, list item, dict value and attribute."""
        self.check_both("big_format_review")

    def build(self, name, env_extra=None):
        text = (CASES / (name + ".py")).read_text(encoding="utf-8")
        src = Path(self.tmp.name) / (name + ".py")
        src.write_text(text, encoding="utf-8")
        exe = Path(self.tmp.name) / ("%s_exe_%s" % (name, "_".join(sorted((env_extra or {}).keys())) or "plain"))
        if exe.exists():
            exe.unlink()
        env = dict(os.environ, AIL_NO_CACHE="1", AIL_QUIET_FALLBACK="1", **(env_extra or {}))
        made = subprocess.run([sys.executable, "-B", str(ROOT / "ail_chatgpt.py"), "compile", str(src), "--syntax", "python",
                               "-o", str(exe)], capture_output=True, text=True, timeout=900, env=env)
        return made, exe, src

    def test_general_program_overflows_mid_loop(self):
        self.check("general_overflow_loop")

    def test_marked_functions_take_the_general_path(self):
        """A function-local `import math` and `math.factorial(30)` (the reviewer's p10), `**` with a variable exponent, `<<` by a
        variable, `int()` of a long string: exact; and the typed path alone refuses them by name."""
        self.check("p10_local_import")
        self.check("marked_function_mixed")

    def build_c(self, name):
        text = (CASES / (name + ".py")).read_text(encoding="utf-8")
        src = Path(self.tmp.name) / (name + ".py")
        src.write_text(text, encoding="utf-8")
        exe = Path(self.tmp.name) / (name + "_cexe")
        dbg = Path(self.tmp.name) / (name + "_cdbg")
        if exe.exists():
            exe.unlink()
        env = dict(os.environ, AIL_NO_CACHE="1", AIL_QUIET_FALLBACK="1")
        made = subprocess.run([sys.executable, "-B", str(ROOT / "ail_chatgpt.py"), "compile", str(src), "--syntax", "python",
                               "-o", str(exe), "--debug-dir", str(dbg)], capture_output=True, text=True, timeout=900, env=env)
        return made, exe, src, dbg / "program.c"

    def test_constant_math_and_float_programs_are_exact(self):
        """Constant comb/perm calls are unproven call results (rule 3), so they are exact on the general path.  Since
        B1b an unproven float parameter or item is bigint-capable, so those programs are exact there too; a program
        whose values the local proof covers still keeps the typed path with no big-int runtime."""
        made, exe, src = self.build("gate_math_constants")
        self.assertEqual(made.returncode, 0, made.stdout[-500:] + made.stderr[-1500:])
        want = subprocess.run([sys.executable, str(src)], capture_output=True, text=True, timeout=300)
        got = subprocess.run([str(exe)], capture_output=True, text=True, timeout=300)
        self.assertEqual(got.stdout, want.stdout, "gate_math_constants")
        self.assertEqual(got.returncode, want.returncode, "gate_math_constants")
        self.assertLess(exe.stat().st_size, 150000, "gate_math_constants")
        for name in ("gate_float_only", "float_params"):
            self.check(name)
        made, exe, src, c = self.build_c("b1_strloop")
        self.assertEqual(made.returncode, 0, made.stdout[-500:] + made.stderr[-1500:])
        want = subprocess.run([sys.executable, str(src)], capture_output=True, text=True, timeout=300)
        got = subprocess.run([str(exe)], capture_output=True, text=True, timeout=300)
        self.assertEqual(got.stdout, want.stdout, "b1_strloop")
        self.assertEqual(got.returncode, want.returncode, "b1_strloop")
        text = c.read_text(encoding="utf-8")
        self.assertNotIn("AIL_T_BIG", text, "b1_strloop")
        self.assertNotIn("ail_big_alloc", text, "b1_strloop")
        self.assertLess(exe.stat().st_size, 120000, "b1_strloop")

    def test_gate_evidence_comes_from_every_store_and_call(self):
        """The size gate sees an int/float mix through a class-body fallback, a default argument and a function passed
        as a value: the field is int arithmetic, not proven float (the reviewer's three probes)."""
        self.check("gate_evidence")
        made, _, _ = self.build("p10_local_import", {"AIL_NO_GENERAL": "1"})
        self.assertNotEqual(made.returncode, 0)
        self.assertIn("beyond int64", made.stdout + made.stderr)

    def test_gate_starred_required_and_class_only_last(self):
        """A starred argument in a method, class-only attributes and a class-only last store with __init__: exact on
        both builds (the follow-up review)."""
        self.check("star_required")
        self.check("class_only_last")

    def check_both(self, name):
        text = (CASES / (name + ".py")).read_text(encoding="utf-8")
        src = Path(self.tmp.name) / (name + ".py")
        src.write_text(text, encoding="utf-8")
        want = subprocess.run([sys.executable, str(src)], capture_output=True, text=True, timeout=300)
        self.assertEqual(want.returncode, 0, want.stderr[-1500:])
        for tag, extra in (("general", {"AIL_UNIFIED_FORCE": "1"}), ("default", {})):
            made, exe, _ = self.build(name, extra)
            self.assertEqual(made.returncode, 0, (name, tag, made.stdout[-500:] + made.stderr[-1500:]))
            got = subprocess.run([str(exe)], capture_output=True, text=True, timeout=300)
            self.assertEqual(got.stdout, want.stdout, (name, tag))
            self.assertEqual(got.returncode, want.returncode, (name, tag))
            self.assertEqual(got.stderr, want.stderr, (name, tag))

    def test_b1_review_probes_on_both_builds(self):
        """Every probe of the earlier reviews, on the forced-general and the default build: starred calls in methods,
        class attributes, comb/perm (constant and not), class-only last assignment with __init__, and the B1 boundary
        probes (argument, list item, dict value, attribute, aliasing, 2**62 edges, empty comb/perm)."""
        for name in ("star_required", "class_only_last", "gate_math_constants", "gate_evidence", "b1_probes",
                     "float_params"):
            self.check_both(name)

    def test_b1_review2_probes_on_both_builds(self):
        """The five findings of the second B1 review: str/items/split loops are not int sources, abs() of a negative
        range, a program class's __len__, an implicit op in an attribute/subscript +=, and an unproven call result that
        is only stored/returned."""
        for name in ("b1_strloop", "b1_absneg", "b1_lenobj", "b1_augattr", "b1_roundbig"):
            self.check_both(name)

    def test_b1_review3_probes_on_both_builds(self):
        """The third review's two holes: `.items()`/`.split()` are non-int only when their receiver is a proven non-int
        container (so dict(enumerate(str)) keys and bytes iteration are int sources), and a `.copy()`/`.split()`/
        `.items()` call is a built-in length only when its receiver is a built-in container.  The fourth review adds a
        dict reached through a list/dict item and a custom `__radd__` in a `len()` argument's `+`."""
        for name in ("b1_itemsint", "b1_lencopy", "b1_itemslist", "b1_itemsarg", "b1_itemsdict", "b1_lenradd"):
            self.check_both(name)

    def test_b1_review5_probes_on_both_builds(self):
        """A custom `.lower()` on an unproven receiver is not a str method: the list of ints it returns is an int
        source both directly and through a dict value, so its keys print exact big ints on both builds."""
        self.check_both("b1_nestedlower")

    def test_b1b_bool_probes_on_both_builds(self):
        """Bools are ints (B1b): a bool sum that grows by squaring at module level, in a function, through a class
        attribute, and as a `**` base print CPython's int on both builds (65536 for the power probe)."""
        for name in ("b1b_boolgrow", "b1b_boolfn", "b1b_boolpow", "b1b_attrbool"):
            self.check_both(name)

    def test_mix_clone_overflow_falls_back(self):
        """An int64-overflowing value inside a mixed clone runs the boxed body (the clone's checked
        helpers longjmp to the wrapper), not the typed loud stop: CPython's exact big int on both builds."""
        made, exe, src, c = self.build_c("mix_clone_overflow")
        self.assertEqual(made.returncode, 0, made.stdout[-500:] + made.stderr[-1500:])
        units = sorted(c.parent.glob("*_mix*.c"))
        self.assertTrue(units, "no typed clone")
        text = "".join(u.read_text(encoding="utf-8") for u in units)
        self.assertIn("longjmp", text)
        self.assertIn("__mix_overflow", text)
        want = subprocess.run([sys.executable, str(src)], capture_output=True, text=True, timeout=300)
        got = subprocess.run([str(exe)], capture_output=True, text=True, timeout=300)
        self.assertEqual(got.stdout, want.stdout)
        self.assertEqual(got.returncode, want.returncode)
        self.assertEqual(got.stderr, want.stderr)
        self.check_both("mix_clone_overflow")

    def test_marked_transitively_and_in_containers(self):
        """The unmarked caller of a marked function, a method, values read back through a list, a dict, an attribute and an
        argument: exact (the o1 / o2 probes of the review)."""
        self.check("marked_transitive")
        self.check("general_containers_exact")
        self.check("module_level_containers")
        self.check("factorial_main")

    def test_unproven_int_overflow_is_exact(self):
        """Rules 2-4: an unboxed int64 local no longer stops loudly on overflow; the function that cannot prove its
        ints uses the general representation on both builds."""
        self.check("general_unboxed_loud_stop")
        self.check("typed_overflow_stops")

    def test_b2_review_probes_on_both_builds(self):
        """The B2b review: a huge range stop is not saturated (step 1, explicit 1, empty, step 2, negative
        step, and a stop read through an argument/list item/attribute/dict value), a missing dict key keeps
        the key as KeyError.args (str/int/negative/bytes/float/empty/tuple and every value source), and two
        typed clones sharing a non-inlinable helper still link and print CPython's answer."""
        for name in ("b2_range_boundary", "b2_range_sources", "b2_keyargs", "b2_mixshare",
                     "b2_mixhelper", "b2_float_plain"):
            self.check_both(name)

    def test_b2_no_int_float_keeps_typed_path(self):
        """A plain float program is not sent to the general path by the tagged-int gate: the default build and
        AIL_NO_GENERAL=1 produce the same binary, with no big-int or tint runtime in the generated C.  This
        includes a module-level float dict read through a local (the review's n2a_float_plain shape)."""
        for name in ("b2_float_simple", "b2_float_module_dict"):
            made, exe, src, c = self.build_c(name)
            self.assertEqual(made.returncode, 0, (name, made.stdout[-500:] + made.stderr[-1500:]))
            text = c.read_text(encoding="utf-8")
            self.assertNotIn("AIL_T_BIG", text, name)
            self.assertNotIn("ail_tint", text, name)
            made_typed, exe_typed, _ = self.build(name, {"AIL_NO_GENERAL": "1"})
            self.assertEqual(made_typed.returncode, 0,
                             (name, made_typed.stdout[-500:] + made_typed.stderr[-1500:]))
            self.assertEqual(exe.stat().st_size, exe_typed.stat().st_size, name + " size")
            want = subprocess.run([sys.executable, str(src)], capture_output=True, text=True, timeout=300)
            for binary in (exe, exe_typed):
                got = subprocess.run([str(binary)], capture_output=True, text=True, timeout=300)
                self.assertEqual(got.stdout, want.stdout, name)
                self.assertEqual(got.returncode, want.returncode, name)


class B3SecondReview(unittest.TestCase):
    """The B3 second review: runtime pieces pulled in by the runtime itself, multi-argument exceptions,
    mutable class attributes created once, and enumerate() with a start beyond int64."""
    @classmethod
    def setUpClass(cls):
        if not CC:
            raise unittest.SkipTest("no C compiler")
        cls.tmp = tempfile.TemporaryDirectory(prefix="ail-b3rev-")

    def compare(self, name, text, env=None, stdin=b"",
                builds=(("default", {}), ("general", {"AIL_UNIFIED_FORCE": "1"}))):
        src = Path(self.tmp.name) / (name + ".py")
        src.write_text(text, encoding="utf-8")
        want = subprocess.run([sys.executable, str(src)], input=stdin, capture_output=True, timeout=300)
        self.assertEqual(want.returncode, 0, want.stderr[-1500:])
        for tag, extra in builds:
            exe = Path(self.tmp.name) / ("%s_%s" % (name, tag))
            if exe.exists():
                exe.unlink()
            e = dict(os.environ, AIL_NO_CACHE="1", AIL_QUIET_FALLBACK="1", **(env or {}))
            e.update(extra)
            made = subprocess.run([sys.executable, "-B", str(ROOT / "ail_chatgpt.py"), "compile", str(src),
                                   "--syntax", "python", "-o", str(exe)], capture_output=True, text=True,
                                  timeout=900, env=e)
            self.assertEqual(made.returncode, 0, (name, tag, made.stdout[-500:] + made.stderr[-2000:]))
            got = subprocess.run([str(exe)], input=stdin, capture_output=True, timeout=300, env=e)
            self.assertEqual(got.stdout, want.stdout, (name, tag))
            self.assertEqual(got.returncode, want.returncode, (name, tag))
            self.assertEqual(got.stderr, want.stderr, (name, tag))

    def test_b3_round_pulls_division_and_power(self):
        """round() of a big int without n<0 uses the runtime's own ail_int_divmod and ail__int_pow; those pieces
        must be linked even though the program text names neither (the review's stdin reproducer, and a literal
        form where `**` does not enable the pow piece by itself)."""
        self.compare("b3_round_pieces",
                     "x = 10**25 + int(input())\n"
                     "y = 10000000000000000000000000 + int(input())\n"
                     "print(round(x, -3), round(y, -3))\n",
                     stdin=b"123456\n123456\n")

    def test_b3_each_runtime_piece_links(self):
        """One minimal program per piece: sys.stdout.write only (no print, no range loop), so a missing dependency
        cannot be hidden by another feature that happens to name the same entry point."""
        big = "1000000000000000000000000000000"
        programs = {
            "div": ("import sys\nx = %s\nsys.stdout.write(str(x // 7) + '\\n')\n"
                    "sys.stdout.write(str(x %% 7) + '\\n')\n"
                    "sys.stdout.write(str(divmod(x, 7)) + '\\n')\n"
                    "sys.stdout.write(str(x / 7) + '\\n')\n" % big),
            "pow": ("import sys\nsys.stdout.write(str(2 ** 100) + '\\n')\n"
                    "sys.stdout.write(str(pow(2, 100, 1000000007)) + '\\n')\n"),
            "shift": ("import sys\nx = %s\nsys.stdout.write(str(x << 40) + '\\n')\n"
                      "sys.stdout.write(str(x >> 40) + '\\n')\n" % big),
            "bits": ("import sys\nx = %s\nsys.stdout.write(str(x & 255) + '\\n')\n"
                     "sys.stdout.write(str(x | 1) + '\\n')\n"
                     "sys.stdout.write(str(x ^ 3) + '\\n')\n"
                     "sys.stdout.write(str(~x) + '\\n')\n" % big),
            "text": ("import sys\nx = %s\nsys.stdout.write(str(x) + '\\n')\n"
                     "sys.stdout.write(hex(x) + '\\n')\n"
                     "sys.stdout.write(bin(x) + '\\n')\n"
                     "sys.stdout.write(oct(x) + '\\n')\n" % big),
        }
        for piece, text in programs.items():
            self.compare("b3_piece_" + piece, text, builds=(("default", {}),))

    def test_b3_multi_argument_exception_str(self):
        """raise E(a, b) caught by name: str(e) is repr of the arguments tuple, for builtin and program classes,
        KeyError's own quirk, and an argument that is itself a big int; both AIL_IR modes."""
        text = (
            "try:\n    raise ValueError(1, 2)\n"
            "except Exception as e:\n    print(type(e).__name__, str(e), repr(e.args))\n"
            "try:\n    raise ValueError('v', 10**25)\n"
            "except Exception as e:\n    print(type(e).__name__, str(e), repr(e.args))\n"
            "try:\n    raise TypeError(1, 2.5, None, True, [1], {'a': 1}, (1, 2))\n"
            "except Exception as e:\n    print(type(e).__name__, str(e), repr(e.args))\n"
            "try:\n    raise KeyError(1, 2)\n"
            "except Exception as e:\n    print(type(e).__name__, str(e), repr(e.args))\n"
            "class E(Exception):\n    pass\n"
            "try:\n    raise E(1, 2)\n"
            "except Exception as e:\n    print(type(e).__name__, str(e), repr(e.args))\n")
        for ir in ("0", "1"):
            self.compare("b3_exc_multi_" + ir, text, {"AIL_IR": ir})

    def test_b3_mutable_class_attribute_is_one_object(self):
        """A list/dict/set/tuple in a class body is built once: repeated reads are the same object, mutations are
        shared by the class and its instances, and an instance rebinding does not replace the class value."""
        text = (
            "class C:\n"
            "    xs = [1, 2, 3]\n"
            "    d = {'a': 1}\n"
            "    s = {1, 2}\n"
            "    t = (1, 2)\n"
            "    n = [[1], [2]]\n"
            "class A:\n    x = [1]\n"
            "class B:\n    x = [1]\n"
            "print(C.xs is C.xs, C.d is C.d, C.s is C.s, C.t is C.t)\n"
            "print(C.n is C.n, C.n[0] is C.n[0], A.x is B.x)\n"
            "C.xs.append(4); C.d['b'] = 2; C.s.add(3); C.n[0].append(5)\n"
            "print(C.xs, sorted(C.d.items()), sorted(C.s), C.t, C.n)\n"
            "o = C()\n"
            "print(o.xs is C.xs, o.d is C.d, o.s is C.s, o.t is C.t, o.n is C.n)\n"
            "o.xs.append(6); o.n[0].append(7)\n"
            "print(C.xs, C.n)\n"
            "o.xs = [9]; o.n = [[8]]\n"
            "print(o.xs, C.xs, o.n is C.n, C.n)\n"
            "def f(a):\n    a.append(99)\n    return a\n"
            "print(f(C.xs), C.xs)\n"
            "dv = {'k': C.xs}\ndv['k'].append(100)\nprint(C.xs)\n")
        self.compare("b3_classattr", text)

    def test_class_attribute_assignment_reproducers(self):
        """`C.attr = v` stores on the one class object (existing and new attributes, empty classes) at module
        level, in a function and in a method; a class reached through a variable and a function argument works
        too.  Both builds must print CPython's answer instead of segfaulting."""
        text = (
            "class C:\n"
            "    a = 1\n"
            "C.a = 5\n"
            "print(C.a)\n"
            "C.k = 5\n"
            "print(C.k)\n"
            "class E:\n"
            "    pass\n"
            "E.k = 5\n"
            "print(E.k)\n"
            "def f():\n"
            "    C.k = 7\n"
            "    return C.k\n"
            "print(f(), C.k)\n"
            "class D:\n"
            "    def set(self):\n"
            "        C.z = 9\n"
            "        return C.z\n"
            "print(D().set(), C.z)\n"
            "K = C\n"
            "K.q = 11\n"
            "print(C.q, K.q, C().q)\n"
            "class H:\n"
            "    pass\n"
            "h = H(); h.v = 3\n"
            "def setit(o, v):\n"
            "    o.v = v\n"
            "setit(C, h.v)\n"
            "print(C.v)\n")
        self.compare("classattr_set_basic", text)

    def test_class_attribute_assignment_instances_and_subclasses(self):
        """A class assignment is visible through an instance made before and after it (until the instance
        shadows it), and through subclasses; assigning on the subclass does not change the base."""
        text = (
            "class C:\n"
            "    a = 1\n"
            "c = C()\n"
            "print(c.a)\n"
            "C.a = 5\n"
            "print(C.a, c.a, C().a)\n"
            "c.a = 10\n"
            "print(c.a, C.a)\n"
            "C.a = 6\n"
            "print(c.a, C.a, C().a)\n"
            "class A:\n"
            "    a = 1\n"
            "class B(A):\n"
            "    pass\n"
            "b = B()\n"
            "print(B.a, b.a)\n"
            "A.a = 2\n"
            "print(A.a, B.a, b.a)\n"
            "B.a = 3\n"
            "print(A.a, B.a, B().a, b.a)\n"
            "class S(A):\n"
            "    a = 9\n"
            "print(A.a, B.a, S.a)\n"
            "S.a = 4\n"
            "print(A.a, B.a, S.a)\n"
            "A.a = 7\n"
            "print(A.a, B.a, S.a)\n"
            "class A2:\n"
            "    a = 1\n"
            "class B2(A2):\n"
            "    pass\n"
            "B2.new = [1]\n"
            "B2.new.append(2)\n"
            "print(B2.new, B2().new, A2.a)\n")
        self.compare("classattr_set_instances", text)

    def test_class_attribute_assignment_values_sources_and_aug(self):
        """Every value kind (big/negative int, float, str, bool, None, list, dict, set, tuple) and a value
        reaching the assignment through an argument, list item, attribute and dict value; mutable class
        values keep identity, an instance rebinding shadows; +=/-=/ *= update the class binding."""
        text = (
            "class C:\n"
            "    pass\n"
            "neg = -(10 ** 30)\n"
            "empty = []\n"
            "d = {'x': 1}\n"
            "s = {1, 2}\n"
            "t = (1, 2)\n"
            "f = 1.5\n"
            "n = None\n"
            "b = True\n"
            "txt = 'a b'\n"
            "C.neg = neg\n"
            "C.empty = empty\n"
            "C.d = d\n"
            "C.s = s\n"
            "C.t = t\n"
            "C.f = f\n"
            "C.n = n\n"
            "C.b = b\n"
            "C.txt = txt\n"
            "print(C.neg, C.empty, C.d, sorted(C.s), C.t, C.f, C.n, C.b, C.txt)\n"
            "print(C().neg, C().empty is C.empty, C().d is C.d)\n"
            "C.neg = -1\n"
            "C.empty.append(3)\n"
            "print(C.neg, C.empty, C().empty)\n"
            "class Holder:\n"
            "    pass\n"
            "def setit(v):\n"
            "    C.v = v\n"
            "h = Holder()\n"
            "h.v = 'attr'\n"
            "items = [10 ** 20]\n"
            "dv = {'v': 2.5}\n"
            "setit(items[0])\n"
            "print(C.v)\n"
            "C.v = items[0] + 1\n"
            "print(C.v)\n"
            "C.v = h.v\n"
            "print(C.v)\n"
            "C.v = dv['v']\n"
            "print(C.v)\n"
            "C.v = [1, 2][1]\n"
            "print(C.v)\n"
            "class M:\n"
            "    xs = [1]\n"
            "    d = {'a': 1}\n"
            "m = M()\n"
            "print(M.xs is M.xs, m.xs is M.xs, m.d is M.d)\n"
            "M.xs.append(2)\n"
            "print(m.xs, M.xs)\n"
            "m.xs = [9]\n"
            "print(m.xs, M.xs)\n"
            "M.xs = [5]\n"
            "print(m.xs, M.xs, m.xs is M.xs)\n"
            "m2 = M()\n"
            "print(m2.xs is M.xs, m2.xs)\n"
            "M.d['b'] = 2\n"
            "print(m2.d, M.d)\n"
            "class Q:\n"
            "    a = 1\n"
            "    xs = [1]\n"
            "Q.a += 4\n"
            "Q.xs += [2]\n"
            "print(Q.a, Q.xs)\n"
            "Q.a *= 2\n"
            "Q.a -= 3\n"
            "print(Q.a, Q.xs is Q.xs)\n"
            "class R(Q):\n"
            "    pass\n"
            "R.a += 1\n"
            "print(Q.a, R.a, R().a)\n")
        self.compare("classattr_set_values", text)

    def test_b3_enumerate_big_start_is_exact(self):
        """enumerate(xs, start) with a start beyond int64, a count crossing int64, a negative big start, and a start
        read through a parameter, list item, attribute and dict value: the index is CPython's int, not a saturated
        or wrapped int64."""
        text = (
            "xs = [10, 20, 30]\n"
            "for i, v in enumerate(xs, 9223372036854775806):\n    print(i, v)\n"
            "for i, v in enumerate(['a', 'b'], -(10**20)):\n    print(i, v)\n"
            "def show(start):\n"
            "    for i, v in enumerate([1, 2], start):\n"
            "        print(i, v)\n"
            "show(10**20)\n"
            "d = {'s': 10**21}\nshow(d['s'])\n"
            "class C:\n    pass\n"
            "c = C(); c.s = 10**22\nshow(c.s)\nshow([10**23][0])\n"
            "for i, v in enumerate([], 10**30):\n    print(i, v)\n"
            "print('empty', 'done')\n"
            "for i, v in enumerate([1, 2, 3], 9223372036854775807):\n    print(i, v)\n"
            "for i, v in enumerate({'a': 1, 'b': 2}, 10**20):\n    print(i, v)\n"
            "for i, v in enumerate(range(3), 10**20):\n    print(i, v)\n"
            "for i, v in enumerate('xy', 10**20):\n    print(i, v)\n")
        self.compare("b3_enum_bigstart", text)

    def test_instance_by_name_lookup_sees_class_attributes(self):
        """getattr()/hasattr() on an instance fall back to the class and its base classes after the instance's own
        table: the review's reproducers, a default for a missing name, a shadowing instance attribute, setattr()
        still writing the instance, a base-class override, and values reached through an argument, list item, dict
        value and attribute.  The missing-name error is CPython's AttributeError text."""
        text = (
            "class C:\n"
            "    a = 1\n"
            "c = C()\n"
            "print(hasattr(c, 'a'))\n"
            "print(getattr(c, 'a'))\n"
            "print(getattr(c, 'zz', 7))\n"
            "try:\n"
            "    getattr(c, 'zz')\n"
            "except AttributeError as e:\n"
            "    print(type(e).__name__, str(e))\n"
            "class A:\n"
            "    a = 1\n"
            "    b = 2\n"
            "class B(A):\n"
            "    b = 20\n"
            "    c = 30\n"
            "class D(B):\n"
            "    pass\n"
            "d = D()\n"
            "print(hasattr(d, 'a'), getattr(d, 'a', 0))\n"
            "print(getattr(d, 'a'), getattr(d, 'b'), getattr(d, 'c'), getattr(d, 'zz', 'D'))\n"
            "d.a = 100\n"
            "print(d.a, hasattr(d, 'a'), getattr(d, 'a'), A.a, C.a)\n"
            "setattr(d, 'a', 7)\n"
            "setattr(d, 'new', 8)\n"
            "print(d.a, hasattr(d, 'new'), getattr(d, 'new'), A.a, D().a)\n"
            "A.a = 5\n"
            "D.a = 50\n"
            "print(A.a, B.a, D.a, d.a, D().a)\n"
            "B.b = 21\n"
            "print(B.b, getattr(d, 'b'), D().b)\n"
            "class Empty:\n"
            "    pass\n"
            "e = Empty()\n"
            "print(hasattr(e, 'a'), getattr(e, 'a', 'none'))\n"
            "class V:\n"
            "    n = -(10 ** 30)\n"
            "    f = 1.5\n"
            "    s = 'txt'\n"
            "    b = True\n"
            "    none = None\n"
            "    xs = []\n"
            "    m = {'k': 1}\n"
            "    st = {1, 2}\n"
            "    t = (1, 2)\n"
            "v = V()\n"
            "print(getattr(v, 'n'), getattr(v, 'f'), getattr(v, 's'), getattr(v, 'b'), getattr(v, 'none'))\n"
            "print(getattr(v, 'xs') is V.xs, getattr(v, 'm') is V.m, getattr(v, 'st') is V.st, getattr(v, 't') is V.t)\n"
            "v.xs.append(3)\n"
            "print(V.xs, getattr(v, 'xs'))\n"
            "class H:\n"
            "    pass\n"
            "h = H()\n"
            "h.a = 10 ** 40\n"
            "items = [7]\n"
            "dv = {'a': 'fromdict'}\n"
            "def get(o, n):\n"
            "    return getattr(o, n, 'D')\n"
            "print(get(v, 'n'), get(v, 'zz'))\n"
            "print(getattr(h, 'a') + 1)\n"
            "items[0] = 8\n"
            "print(getattr(v, 'zz', items[0]))\n"
            "print(getattr(v, 'zz', dv['a']))\n"
            "print(getattr(v, 'zz', h.a))\n"
            "names = ['a', 'zz']\n"
            "print(getattr(D(), names[0]), hasattr(D(), names[0]), hasattr(D(), names[1]))\n"
            "h.obj = d\n"
            "print(getattr(h.obj, 'b'))\n"
            "try:\n"
            "    getattr(d, 1)\n"
            "except TypeError as e:\n"
            "    print(type(e).__name__, str(e))\n")
        self.compare("instance_by_name_class_fallback", text)


class MarkRules(unittest.TestCase):
    """bigcap.marked: which functions are big-int capable (docs/design/BIGINT.md sections 4-5)."""
    SRC = """
import math
def lit(): return 12345678901234567890123
def pow_var(a, b): return a ** b
def pow_big(): return 10 ** 19
def pow_ok(): return 10 ** 18
def pow_small_base(x): return x ** 3
def pow_4(x): return x ** 4
def pow_float(x): return x ** 0.5
def shl_var(n): return 1 << n
def shl_const(x): return x << 3
def fact(n): return math.factorial(n)
def fact5(): return math.factorial(5)
def fact21(): return math.factorial(21)
def comb2(n, k): return math.comb(n, k)
def comb_small(): return math.comb(10, 3)
def perm_small(): return math.perm(10, 3)
def comb_fit1(): return math.comb(1001, 1)
def perm_fit(): return math.perm(2000, 1)
def comb_fit2(): return math.comb(5000, 1)
def comb_fit_edge(): return math.comb(66, 33)
def perm_fit_edge(): return math.perm(20, 20)
def comb_over(): return math.comb(68, 34)
def perm_over(): return math.perm(21, 21)
def int_long(): return int("1234567890123456789")
def int_short(): return int("123456789012345678")
def from_b(b): return int.from_bytes(b, "big")
def pow2(a, b): return pow(a, b)
def pow3(a, b, m): return pow(a, b, m)
def caller(n): return fact(n) + 1
def caller2(n): return caller(n)
class K:
    def meth(self, n): return fact(n)
    def plain(self): return 1
def user(k, n): return k.meth(n)
def inner():
    def deep(n): return n ** n
    return 1
def clean(a, b): return a * b + a - b
def local_mul(n): return n * n
def local_add(n): return n + 1
def local_float(x): return x * 2.0
def local_float_lit():
    x = 1.5
    return x * x
def local_len(s): return len(s) + 1
def local_item(xs): return xs[0] * xs[1]
def local_attr(o): return o.x * o.x
def local_int_str(s): return int(s)
def local_range():
    s = 0
    for i in range(10):
        s += i
    return s
def local_comb(): return math.comb(10, 3)
def local_pow_const(): return 10 ** 18
def plain2(): return 1
"""
    @classmethod
    def setUpClass(cls):
        import ast
        import bigcap
        os.environ["AIL_SURFACE"] = "python"
        cls.marks = bigcap.marked(ast.parse(cls.SRC))

    @classmethod
    def tearDownClass(cls):
        os.environ.pop("AIL_SURFACE", None)

    def test_marked(self):
        for name in ("lit", "pow_var", "pow_big", "pow_small_base", "pow_4", "shl_var", "shl_const", "fact",
                     "fact5", "fact21", "comb2", "comb_small", "perm_small", "comb_fit1", "perm_fit", "comb_fit2",
                     "comb_fit_edge", "perm_fit_edge", "comb_over", "perm_over", "int_long", "int_short", "from_b",
                     "pow2", "pow3", "caller", "caller2", "meth", "user", "inner", "deep", "clean", "local_mul",
                     "local_add", "local_item", "local_attr", "local_int_str", "local_range", "local_comb"):
            self.assertIn(name, self.marks, name)

    def test_not_marked(self):
        for name in ("pow_ok", "pow_float", "plain", "plain2", "local_float", "local_float_lit", "local_len",
                     "local_pow_const"):
            self.assertNotIn(name, self.marks, name)

    def test_local_proof_wins_over_call_sites_and_containers(self):
        """Rules 3-4: an attribute, a list item, a dict value and a parameter are unproven (so marked), while a local
        whose only values are literals, len(), or float arithmetic is kept."""
        import ast
        import bigcap
        os.environ["AIL_SURFACE"] = "python"
        try:
            marks = bigcap.marked(ast.parse(self.SRC))
            self.assertIn("local_attr", marks)
            self.assertIn("local_item", marks)
            self.assertIn("local_mul", marks)
            self.assertNotIn("local_float", marks)
            self.assertNotIn("local_len", marks)
            self.assertNotIn("local_float_lit", marks)
        finally:
            os.environ["AIL_SURFACE"] = "python"

    def test_constant_math_is_unproven(self):
        """A call result is unproven by rule 3 even when its constant arguments would fit: no `_math_call_fits`."""
        import ast
        import bigcap
        os.environ["AIL_SURFACE"] = "python"
        try:
            for src in ("import math\ndef f(): return math.comb(10, 3)", "import math\ndef f(): return math.factorial(5)",
                        "import math\ndef f(): return math.perm(10, 3)", "def f(s): return int('123')"):
                self.assertTrue(bigcap.marked(ast.parse(src)))
        finally:
            os.environ["AIL_SURFACE"] = "python"

    def test_the_module_code_counts(self):
        import ast
        import bigcap
        self.assertIn("<module>", bigcap.marked(ast.parse("print(2 ** n)")))
        self.assertNotIn("<module>", bigcap.marked(ast.parse("def f(): return 2 ** n\nprint(1)")) )

    def test_missing_knowledge_is_bigint_capable(self):
        """B1b: there is no global pre-gate.  An unproven parameter, item or attribute is bigint-capable even when the
        call sites pass floats; values the local proofs cover (a float literal, a float exponent) stay unmarked."""
        import ast
        import bigcap
        os.environ["AIL_SURFACE"] = "python"
        try:
            self.assertEqual(bigcap.marked(ast.parse((CASES / "b1_strloop.py").read_text(encoding="utf-8"))), {})
            for src in ("def f(x): return x ** 0.5\nprint(f(2.0))\n",
                        "def f():\n    x = 1.5\n    return x * x\nprint(f())\n"):
                self.assertEqual(bigcap.marked(ast.parse(src)), {}, src)
            for src in ("def area(a, b): return a * b\nprint(area(3.5, 2.0))\n",
                        "def f(xs): return xs[0] * xs[1]\nprint(f([3.5, 2.0]))\n",
                        "def f(x): return x + 1\nprint(f(2.0))\n",
                        "def f(xs): return xs[0] * xs[1]\nprint(f([3037000500, 3037000500]))\n",
                        "import sys\nprint(sys.maxsize * sys.maxsize)\n"):
                self.assertTrue(bigcap.marked(ast.parse(src)), src)
            for name in ("gate_float_only", "float_params"):
                self.assertTrue(bigcap.marked(ast.parse((CASES / (name + ".py")).read_text(encoding="utf-8"))), name)
        finally:
            os.environ["AIL_SURFACE"] = "python"

    def test_b1b_bools_are_ints(self):
        """A bool sum is int arithmetic: the growing module code, function, class attribute and power probes are all
        marked now that the pre-gate cannot return early."""
        import ast
        import bigcap
        os.environ["AIL_SURFACE"] = "python"
        try:
            for name in ("b1b_boolgrow", "b1b_boolfn", "b1b_boolpow", "b1b_attrbool"):
                marks = bigcap.marked(ast.parse((CASES / (name + ".py")).read_text(encoding="utf-8")))
                self.assertIn("<module>", marks, name)
        finally:
            os.environ.pop("AIL_SURFACE", None)

    def test_b1_review2_marks(self):
        """The second review's five findings at the marking level: a str/items/split loop is covered by the local
        proof; abs() of a negative interval is positive; a custom __len__ is unproven; attribute/subscript += checks
        its implicit operator; and round()/get() results are unproven even when only assigned or returned."""
        import ast
        import bigcap
        os.environ["AIL_SURFACE"] = "python"
        try:
            loop = ast.parse((CASES / "b1_strloop.py").read_text(encoding="utf-8"))
            self.assertEqual(bigcap.marked(loop), {})
            marks = bigcap.marked(ast.parse((CASES / "b1_absneg.py").read_text(encoding="utf-8")))
            for name in ("neg_overflow", "neg_twice", "pos_overflow"):
                self.assertIn(name, marks)
            for name in ("neg_edge", "neg_small"):
                self.assertNotIn(name, marks)
            marks = bigcap.marked(ast.parse((CASES / "b1_lenobj.py").read_text(encoding="utf-8")))
            for name in ("direct", "via_arg", "via_item", "via_attr", "via_dict", "small_custom", "builtin_len"):
                self.assertIn(name, marks)
            self.assertNotIn("f", bigcap.marked(ast.parse("def f(s): return len(s) + 1\n")))
            marks = bigcap.marked(ast.parse((CASES / "b1_augattr.py").read_text(encoding="utf-8")))
            for name in ("bump", "add", "bump_item", "bump_dict"):
                self.assertIn(name, marks)
            self.assertNotIn("scale", marks)
            marks = bigcap.marked(ast.parse((CASES / "b1_roundbig.py").read_text(encoding="utf-8")))
            for name in ("one", "assigned", "through_list", "through_attr"):
                self.assertIn(name, marks)
            for name in ("safe_call", "safe_split", "safe_len"):
                self.assertNotIn(name, marks)
        finally:
            os.environ.pop("AIL_SURFACE", None)

    def test_b1_review3_marks(self):
        """`.items()` carries its dict's keys and values and `.split()` carries its receiver's elements, so both are
        non-int only when the receiver is a proven non-int container; a method's built-in-length shape needs a proven
        built-in receiver, not just a method name.  An item reached through a list/dict subscript is a value, not a
        proven non-int container, and `+` is a built-in length only when both operands are."""
        import ast
        import bigcap
        os.environ["AIL_SURFACE"] = "python"
        try:
            for src in ("d = dict(enumerate('xxxxxxxxxxxxxxxxxxxxx'))\nfor k, v in d.items():\n    print(k ** k)\n",
                        "for x in b'a'.split()[0]:\n    print(x ** x)\n",
                        "for k, v in [dict(enumerate('xxxxxxxxxxxxxxxxxxxxx'))][0].items():\n    print(k ** k)\n",
                        "for k, v in {'x': dict(enumerate('xxxxxxxxxxxxxxxxxxxxx'))}['x'].items():\n    print(k ** k)\n"):
                self.assertTrue(bigcap.marked(ast.parse(src)), src)
            for src in ("for k, v in {'a': 1.5}.items():\n    print(v)\n",
                        "for x in 'a b'.split():\n    print(x)\n"):
                self.assertEqual(bigcap.marked(ast.parse(src)), {}, src)
            marks = bigcap.marked(ast.parse((CASES / "b1_itemsint.py").read_text(encoding="utf-8")))
            self.assertIn("<module>", marks)
            marks = bigcap.marked(ast.parse((CASES / "b1_lencopy.py").read_text(encoding="utf-8")))
            for name in ("via_copy", "via_split", "via_items"):
                self.assertIn(name, marks)
            self.assertNotIn("f", bigcap.marked(ast.parse("def f(): return len([1.5].copy()) + 1\n")))
            len_add = ("class R:\n"
                       "    def __radd__(self, other):\n        return self\n"
                       "    def __len__(self):\n        return 4611686018427387904\n"
                       "def f():\n    n = len('a' + R())\n    return n * 2\n")
            self.assertIn("f", bigcap.marked(ast.parse(len_add)))
            self.assertNotIn("f", bigcap.marked(ast.parse("def f(): return len('a' + 'b') * 2\n")))
        finally:
            os.environ.pop("AIL_SURFACE", None)

    def test_b1_review5_marks(self):
        """A str method is a non-int container only when its receiver is syntactically a str.  A program class's
        `.lower()` returning a list of ints is an int source directly and through a dict value; `"ABC".lower()` and
        a concatenation of literals stay non-int."""
        import ast
        import bigcap
        os.environ["AIL_SURFACE"] = "python"
        try:
            head = ("class C:\n"
                    "    def lower(self):\n        return list(dict(enumerate('x' * 21)))\n")
            for src in (head + "d = {'a': C().lower()}\nfor k in d['a']:\n    print(k ** k)\n",
                        head + "for k in C().lower():\n    print(k ** k)\n"):
                self.assertTrue(bigcap.marked(ast.parse(src)), src)
            for src in ("for ch in 'ABC'.lower():\n    print(ch)\n",
                        "for ch in ('A' + 'BC').lower():\n    print(ch)\n"):
                self.assertEqual(bigcap.marked(ast.parse(src)), {}, src)
        finally:
            os.environ.pop("AIL_SURFACE", None)

    def test_ail_syntax_programs_keep_int64(self):
        import ast
        import bigcap
        os.environ.pop("AIL_SURFACE", None)
        try:
            self.assertEqual(bigcap.marked(ast.parse("def f(n): return 1 << n")), {})
        finally:
            os.environ["AIL_SURFACE"] = "python"


if __name__ == "__main__":
    unittest.main()
