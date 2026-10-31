"""Stage T3b of docs/design/TYPED_ARRAY.md: int64 and bool_ arrays, wrapping forms, comparisons, where, take/put, strided
gather/scatter, segmented reductions, the flat f32/f64 matmul `mm` and the dtype promotion helpers.

* reference (CPython only): `ail_array.py` against the PyTorch CPU oracle outputs committed in array_t3b_data/torch_oracle.json
  (written by tools/gen_torch_oracle_t3b.py, never needs torch here), and against independent implementations (Python ints,
  Fractions, naive loops);
* prelude (CPython only): the 64-bit helpers of prelude_ailarray.py (limb multiply, exact sums, float to int64) against Python ints;
* white box (CPython only): the lowered text of array_t3b_cases/*.py and of a program generated from the oracle data, run by CPython
  with no `ail_array.py` beside it, prints what the reference prints;
* native: the same programs built by the compiler (default build and AIL_UNIFIED_FORCE=1; typed-only for typed64.py) print the same
  bytes as CPython with the reference, and the oracle program prints what PyTorch computed;
* refusals: what the lowering does not build is refused by name with file:line and `write instead:`.
"""
import json
import math
import os
import random
import shutil
import struct
import subprocess
import sys
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from fractions import Fraction
from pathlib import Path

ROOT = Path(__file__).resolve().parent
PKG = ROOT / "python" / "pkg-v12"
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(PKG))
import ail_array as ta  # noqa: E402
import ailarray  # noqa: E402
import prelude_ailarray as P  # noqa: E402

CASES = ROOT / "array_t3b_cases"
ORACLE = json.loads((ROOT / "array_t3b_data" / "torch_oracle.json").read_text(encoding="utf-8"))
CC = os.environ.get("PIPE_CC") or shutil.which("cc") or shutil.which("gcc")
NAMES = sorted(p.stem for p in CASES.glob("*.py"))
LO, HI = -(1 << 63), (1 << 63) - 1
DT = {"f16": ta.f16, "f32": ta.f32, "f64": ta.f64, "int8": ta.int8, "int32": ta.int32, "int64": ta.int64, "bool": ta.bool_}


def fl(dt, h):
    return struct.unpack("<" + dt.code, bytes.fromhex(h))[0]


def farr(dt, hexes):
    return ta.frombytes(b"".join(bytes.fromhex(h) for h in hexes), dt)


def hexes(a):
    size = a.dtype.itemsize
    raw = a.tobytes()
    return [raw[k:k + size].hex() for k in range(0, len(raw), size)]


def i64(values):
    return ta.array(values, ta.int64)


# ---- reference against the PyTorch oracle -----------------------------------------------------------------------------
class Oracle(unittest.TestCase):
    def test_header_names_the_torch_version(self):
        self.assertIn("2.15", ORACLE["meta"]["torch"])
        self.assertIn("ATEN_CPU_CAPABILITY=default", ORACLE["meta"]["config"])

    def test_int64_binary_wraps_like_torch_and_raises_by_default(self):
        wrap = {"add": ta.wrapping_add, "sub": ta.wrapping_sub, "mul": ta.wrapping_mul, "floordiv": ta.wrapping_floordiv}
        plain = {"add": lambda a, b: a + b, "sub": lambda a, b: a - b, "mul": lambda a, b: a * b,
                 "floordiv": lambda a, b: a // b, "mod": lambda a, b: a % b}
        exact = {"add": lambda a, b: a + b, "sub": lambda a, b: a - b, "mul": lambda a, b: a * b,
                 "floordiv": lambda a, b: a // b, "mod": lambda a, b: a % b}
        seen = {"wrapped": 0, "raised": 0}
        for op, a, b, want in ORACLE["int64_binary"]:
            A, B = i64([a]), i64([b])
            if op in wrap:
                self.assertEqual(wrap[op](A, B)[0], want, (op, a, b))
            e = exact[op](a, b)
            if LO <= e <= HI:
                self.assertEqual(e, want)
                self.assertEqual(plain[op](A, B)[0], want, (op, a, b))
            else:
                seen["raised"] += 1
                self.assertNotEqual(e, want)
                with self.assertRaises(OverflowError):
                    plain[op](A, B)
        self.assertGreater(seen["raised"], 100)       # the sweep really crosses the boundary

    def test_int64_unary(self):
        for name, a, want in ORACLE["int64_unary"]:
            A = i64([a])
            got = ta.wrapping_neg(A) if name == "neg" else ta.wrapping_abs(A)
            self.assertEqual(got[0], want)
            if a == LO:
                with self.assertRaises(OverflowError):
                    (-A) if name == "neg" else abs(A)
            else:
                self.assertEqual((-A if name == "neg" else abs(A))[0], want)

    def test_int64_sums_and_dots(self):
        for c in ORACLE["int64_sums"]:
            A, B = i64(c["values"]), i64(c["other"])
            self.assertEqual(ta.wrapping_sum(A), c["sum"])
            self.assertEqual(ta.wrapping_dot(A, B), c["dot"])
            if LO <= sum(c["values"]) <= HI:
                self.assertEqual(ta.sum(A), c["sum"])
            else:
                with self.assertRaises(OverflowError):
                    ta.sum(A)

    def test_put_accumulate_wraps_like_index_put(self):
        c = ORACLE["int64_put_accumulate"]
        a = ta.zeros(3, ta.int64)
        ta.put(a, i64(c["idx"]), i64(c["src"]), accumulate=True, overflow="wrap")
        self.assertEqual(a.tolist(), c["result"])
        b = ta.zeros(3, ta.int64)
        with self.assertRaises(OverflowError):
            ta.put(b, i64(c["idx"]), i64(c["src"]), accumulate=True)

    def test_casts(self):
        c = ORACLE["casts"]
        big = i64(c["ints"])
        self.assertEqual(hexes(big.astype(ta.f64)), c["to_f64"])
        self.assertEqual(hexes(big.astype(ta.f32)), c["to_f32"])         # one rounding, not int -> f64 -> f32
        self.assertEqual(hexes(big.astype(ta.f16)), c["to_f16"])
        self.assertEqual(big.astype(ta.int8, "trunc", "wrap").tolist(), c["to_int8"])
        self.assertEqual(big.astype(ta.int32, "trunc", "wrap").tolist(), c["to_int32"])
        self.assertEqual(big.astype(ta.bool_).tolist(), c["to_bool"])
        fs = farr(ta.f64, c["floats"])
        self.assertEqual(fs.astype(ta.bool_).tolist(), c["f64_to_bool"])
        inr = farr(ta.f64, c["f64_in_range"])
        self.assertEqual(inr.astype(ta.int64).tolist(), c["f64_to_int64_trunc"])
        self.assertEqual(farr(ta.f32, c["f32_values"]).astype(ta.bool_).tolist(), c["f32_to_bool"])
        b = ta.array([True, False, True], ta.bool_)
        self.assertEqual(b.astype(ta.int64).tolist(), c["bool_to_int64"])
        self.assertEqual(hexes(b.astype(ta.f32)), c["bool_to_f32"])

    def test_the_double_rounding_trap_is_real(self):
        # 2^62 + 2^38 + 1 is above the f32 tie, but rounds to the tie through f64 first
        v = (1 << 62) + (1 << 38) + 1
        once = i64([v]).astype(ta.f32)[0]
        twice = ta.array([float(v)], ta.f32)[0]
        self.assertNotEqual(once, twice)
        self.assertEqual(once, float(1 << 62) + float(1 << 39))

    def test_compare_f32_ieee_and_scalar_stored_first(self):
        for row in ORACLE["compare_f32"]:
            a, b = farr(ta.f32, row["a"]), farr(ta.f32, row["b"])
            fn = getattr(ta, row["op"])
            self.assertEqual(fn(a, b).tolist(), row["array"], row["op"])
            self.assertEqual(fn(a, row["scalar"]).tolist(), row["scalar_result"], row["op"])
            self.assertEqual(fn(a, row["scalar2"]).tolist(), row["scalar2_result"], row["op"])

    def test_compare_int64(self):
        for row in ORACLE["compare_int64"]:
            fn = getattr(ta, row["op"])
            self.assertEqual(fn(i64(row["a"]), i64(row["b"])).tolist(), row["result"], row["op"])
            self.assertEqual(fn(i64(row["a"]), row["scalar"]).tolist(), row["scalar_result"], row["op"])

    def test_bool_logic_where_any_all(self):
        o = ORACLE["bool"]
        a, b = ta.array(o["a"], ta.bool_), ta.array(o["b"], ta.bool_)
        self.assertEqual(ta.logical_and(a, b).tolist(), o["and"])
        self.assertEqual(ta.logical_or(a, b).tolist(), o["or"])
        self.assertEqual(ta.logical_xor(a, b).tolist(), o["xor"])
        self.assertEqual(ta.logical_not(a).tolist(), o["not"])
        # torch: bool + bool is or, bool * bool is and; the module has no bool arithmetic, the torch layer calls logical_*
        self.assertEqual(ta.logical_or(a, b).tolist(), o["add"])
        self.assertEqual(ta.logical_and(a, b).tolist(), o["mul"])
        self.assertEqual(ta.sum(a), o["sum"])
        self.assertEqual(o["sum_dtype"], "torch.int64")
        self.assertIsInstance(ta.sum(a), int)
        self.assertEqual([ta.any(a), ta.any(ta.zeros(3, ta.bool_)), ta.any(ta.zeros(0, ta.bool_))], o["any"])
        self.assertEqual([ta.all(a), ta.all(ta.full(3, True, ta.bool_)), ta.all(ta.zeros(0, ta.bool_))], o["all"])
        self.assertEqual(ta.any(ta.array([0.0, float("nan")], ta.f32)), o["any_float_nan"])
        self.assertEqual(ta.all(ta.array([1.0, -0.0], ta.f32)), o["all_float_zero"])
        x = ta.array([1.5, 2.5, 3.5, 4.5], ta.f32)
        y = ta.array([-1.0, -2.0, -3.0, -4.0], ta.f32)
        self.assertEqual(hexes(ta.where(a, x, y)), o["where_f32"])
        self.assertEqual(o["sub_error"], "NotImplementedError")       # torch refuses bool - bool and -bool; so does the module
        self.assertEqual(o["neg_error"], "NotImplementedError")
        with self.assertRaises(TypeError):
            a - b
        with self.assertRaises(TypeError):
            -a

    def test_promote_types_is_torchs_table(self):
        for x, row in ORACLE["promote_types"].items():
            for y, want in row.items():
                self.assertIs(ta.promote_types(DT[x], DT[y]), DT[want], (x, y))

    def test_promote_scalar_is_torchs_rule(self):
        scal = {"True": True, "1": 1, "1.5": 1.5}
        for x, row in ORACLE["promote_scalar"].items():
            for k, want in row.items():
                self.assertIs(ta.promote_scalar(DT[x], scal[k]), DT[want], (x, k))
        for x, want in ORACLE["promote_scalar_mul_true"].items():
            self.assertIs(ta.promote_scalar(DT[x], True), DT[want], x)
        self.assertIs(ta.promote_scalar(ta.int64, 2.5, ta.f64), ta.f64)            # set_default_dtype(float64)

    def test_take_and_put_texts_and_results(self):
        x = farr(ta.f32, ORACLE["take"]["x"])
        for c in ORACLE["take"]["cases"]:
            idx = i64(c["idx"])
            if "error" in c:
                with self.assertRaises(IndexError) as cm:
                    ta.take(x, idx)
                self.assertEqual(str(cm.exception), c["error"][1])
                self.assertEqual(c["error"][0], "IndexError")
            else:
                self.assertEqual(hexes(ta.take(x, idx)), c["result"], c["idx"])
        base = farr(ta.f32, ORACLE["put"]["x"])
        for c in ORACLE["put"]["cases"]:
            y = base.copy()
            idx, src = i64(c["idx"]), ta.array(c["src"], ta.f32)
            if "error" in c:
                with self.assertRaises(IndexError) as cm:
                    ta.put(y, idx, src, accumulate=c["accumulate"])
                self.assertEqual(str(cm.exception), c["error"][1])
                self.assertEqual(hexes(y), c["after"])           # the elements before the bad index are written, as in torch
            else:
                ta.put(y, idx, src, accumulate=c["accumulate"])
                self.assertEqual(hexes(y), c["result"], c)

    def test_gather_and_scatter_strided_equal_as_strided(self):
        g = ORACLE["gather_strided"]
        base = farr(ta.f64, g["base"])
        for c in g["cases"]:
            if "torch_error" in c:
                with self.assertRaises(IndexError):
                    ta.gather_strided(base, c["offset"], c["shape"], c["strides"])
            else:
                self.assertEqual(hexes(ta.gather_strided(base, c["offset"], c["shape"], c["strides"])), c["result"], c)
        for c in ORACLE["scatter_strided"]["cases"]:
            z = ta.zeros(24, ta.f64)
            src = farr(ta.f64, c["src"])
            if "torch_error" in c:
                with self.assertRaises(IndexError):
                    ta.scatter_strided(z, c["offset"], c["shape"], c["strides"], src)
                self.assertEqual(z.tolist(), [0.0] * 24)
            else:
                ta.scatter_strided(z, c["offset"], c["shape"], c["strides"], src)
                self.assertEqual(hexes(z), c["result"], c)

    def test_segments(self):
        s = ORACLE["segments"]
        offs = i64(s["offsets"])
        v = farr(ta.f32, s["values"])
        self.assertEqual(hexes(ta.segment_sum(v, offs)), s["sum_f32"])
        iv = i64(s["int_values"])
        self.assertEqual(ta.wrapping_segment_sum(iv, offs).tolist(), s["sum_int64"])       # torch wraps; segment_sum raises
        with self.assertRaisesRegex(OverflowError, "int64 segment_sum overflow at segment 3"):
            ta.segment_sum(iv, offs)
        nonempty = i64([0, 3, 7, 10])
        self.assertEqual([x for x in s["max"] if x is not None], hexes(ta.segment_max(v, nonempty)))
        self.assertEqual([x for x in s["min"] if x is not None], hexes(ta.segment_min(v, nonempty)))
        self.assertEqual([x for x in s["argmax"] if x is not None], ta.segment_argmax(v, nonempty).tolist())
        self.assertEqual([x for x in s["argmin"] if x is not None], ta.segment_argmin(v, nonempty).tolist())
        with self.assertRaisesRegex(ValueError, "segment 1 is empty"):
            ta.segment_max(v, offs)          # torch has no max of an empty slice either
        n = s["nan"]
        nv = farr(ta.f32, n["values"])
        one = i64([0, 5])
        self.assertEqual(hexes(ta.segment_max(nv, one)), [n["max"]])
        self.assertEqual(hexes(ta.segment_min(nv, one)), [n["min"]])
        self.assertEqual(ta.segment_argmax(nv, one).tolist(), [n["argmax"]])
        self.assertEqual(ta.segment_argmin(nv, one).tolist(), [n["argmin"]])

    def test_mm_f32_against_torch(self):
        u = 2.0 ** -24
        for c in ORACLE["mm_f32"]:
            m, k, n = c["m"], c["k"], c["n"]
            a, b = farr(ta.f32, c["a"]), farr(ta.f32, c["b"])
            got = ta.mm(a, b, m, k, n)
            want = farr(ta.f32, c["result"])
            if c["integer"]:
                self.assertEqual(hexes(got), hexes(want), (m, k, n))        # exact in any order
                continue
            av, bv = a.tolist(), b.tolist()
            g = k * u / (1 - k * u)
            for i in range(m):
                for j in range(n):
                    bound = g * sum(abs(av[i * k + t] * bv[t * n + j]) for t in range(k))
                    self.assertLessEqual(abs(got[i * n + j] - want[i * n + j]), 2 * bound + 1e-30, (i, j))


# ---- reference against independent computations --------------------------------------------------------------------
class Independent(unittest.TestCase):
    def test_int64_ops_equal_python_ints(self):
        rng = random.Random(3)
        edge = [LO, LO + 1, -(1 << 62), -(1 << 32), -3037000500, -2, -1, 0, 1, 2, 3037000500, 1 << 32, 1 << 62, HI - 1, HI]
        vals = edge + [rng.randint(LO, HI) for _ in range(40)] + [rng.randint(-(1 << 40), 1 << 40) for _ in range(20)]
        xs = [x for x in vals for _ in vals]
        ys = [y for _ in vals for y in vals]
        A, B = i64(xs), i64(ys)
        wrap = lambda v: ((v - LO) % (1 << 64)) + LO
        self.assertEqual(ta.wrapping_add(A, B).tolist(), [wrap(x + y) for x, y in zip(xs, ys)])
        self.assertEqual(ta.wrapping_sub(A, B).tolist(), [wrap(x - y) for x, y in zip(xs, ys)])
        self.assertEqual(ta.wrapping_mul(A, B).tolist(), [wrap(x * y) for x, y in zip(xs, ys)])
        sat = lambda v: max(LO, min(HI, v))
        self.assertEqual(ta.saturating_add(A, B).tolist(), [sat(x + y) for x, y in zip(xs, ys)])
        self.assertEqual(ta.saturating_sub(A, B).tolist(), [sat(x - y) for x, y in zip(xs, ys)])

    def test_default_ops_raise_at_the_first_bad_index(self):
        a, b = i64([1, HI, 3, LO]), i64([1, 1, 1, -1])
        with self.assertRaisesRegex(OverflowError, "int64 add overflow at index 1"):
            a + b
        with self.assertRaisesRegex(OverflowError, "int64 floordiv overflow at index 1"):
            i64([5, LO]) // i64([2, -1])
        with self.assertRaisesRegex(ZeroDivisionError, "integer division or modulo by zero"):
            a // i64([1, 1, 0, 1])
        c = i64([1, 2, HI, 4, 5])
        with self.assertRaises(OverflowError):
            c += 1
        self.assertEqual(c.tolist(), [2, 3, HI, 4, 5])             # the prefix is updated, as for the other int dtypes

    def test_wrapping_floordiv_only_min_over_minus_one_differs(self):
        xs = [LO, LO, 7, -7, HI]
        ys = [-1, 2, -2, 2, -1]
        self.assertEqual(ta.wrapping_floordiv(i64(xs), i64(ys)).tolist(), [LO, LO // 2, -4, -4, -HI])
        with self.assertRaises(ZeroDivisionError):
            ta.wrapping_floordiv(i64([1]), 0)

    def test_value_checks_of_the_store_rule(self):
        with self.assertRaisesRegex(OverflowError, "int64 value out of range: 9223372036854775808"):
            i64([HI + 1])
        with self.assertRaisesRegex(OverflowError, "int64 value out of range: -9223372036854775809"):
            i64([LO - 1])
        with self.assertRaises(TypeError):
            i64([1.5])
        self.assertEqual(ta.array([2, 0, -1, True], ta.bool_).tolist(), [True, False, True, True])
        with self.assertRaises(TypeError):
            ta.array([1.5], ta.bool_)
        self.assertEqual(ta.frombytes(bytes([0, 1, 2, 255]), ta.bool_).tobytes(), bytes([0, 1, 1, 1]))

    def test_bytes_round_trip(self):
        a = i64([LO, -1, 0, 1, HI, 0x0102030405060708])
        self.assertEqual(ta.frombytes(a.tobytes(), ta.int64), a)
        self.assertEqual(a.tobytes()[:8], (LO).to_bytes(8, "little", signed=True))
        self.assertEqual(ta.zeros(3, ta.bool_).tobytes(), b"\x00\x00\x00")

    def test_astype_int64_to_float_rounds_once(self):
        rng = random.Random(9)
        def exact_round(v, p, emax):
            q = Fraction(abs(v))
            e = q.numerator.bit_length() - 1
            m = q / Fraction(2) ** (e - p + 1)
            fl = m.numerator // m.denominator
            r = m - fl
            if r > Fraction(1, 2) or (r == Fraction(1, 2) and fl % 2):
                fl += 1
            val = Fraction(fl) * Fraction(2) ** (e - p + 1)
            if val >= Fraction(2) ** (emax + 1):
                return math.inf if v > 0 else -math.inf
            return float(val) if v > 0 else -float(val)
        vals = [rng.randint(LO, HI) for _ in range(400)] + [(1 << k) + d for k in range(24, 63)
                                                                  for d in (-1, 0, 1, 1 << (k - 24), (1 << (k - 25)) if k > 24 else 3,
                                                                            ((1 << (k - 25)) + 1) if k > 24 else 5)]
        vals = [v for v in vals if v != 0 and LO <= v <= HI]
        a = i64(vals)
        self.assertEqual(a.astype(ta.f32).tolist(), [exact_round(v, 24, 127) for v in vals])
        self.assertEqual(a.astype(ta.f16).tolist(), [exact_round(v, 11, 15) for v in vals])
        self.assertEqual(a.astype(ta.f64).tolist(), [float(v) for v in vals])

    def test_astype_float_to_int64(self):
        a = ta.array([0.5, -0.5, 1.5, 2.5, 1e18, -9223372036854775808.0], ta.f64)
        self.assertEqual(a.astype(ta.int64).tolist(), [0, 0, 1, 2, 10 ** 18, LO])
        self.assertEqual(a.astype(ta.int64, "nearest").tolist(), [0, 0, 2, 2, 10 ** 18, LO])
        with self.assertRaisesRegex(OverflowError, "int64 cast overflow at index 1"):
            ta.array([1.0, 9223372036854775808.0], ta.f64).astype(ta.int64)
        self.assertEqual(ta.array([9223372036854775808.0, -1e30, float("nan")], ta.f64).astype(ta.int64, "trunc", "saturate").tolist(),
                         [HI, LO, 0])

    def test_where_texts(self):
        m = ta.array([True, False], ta.bool_)
        with self.assertRaisesRegex(TypeError, "needs a bool_ array as the mask, not int64"):
            ta.where(i64([1, 0]), i64([1, 2]), i64([3, 4]))
        with self.assertRaisesRegex(ValueError, "shapes differ: \\(2,\\) and \\(3,\\)"):
            ta.where(m, i64([1, 2, 3]), i64([1, 2, 3]))
        with self.assertRaisesRegex(TypeError, "dtypes differ"):
            ta.where(m, i64([1, 2]), ta.array([1.0, 2.0], ta.f64))
        self.assertEqual(ta.where(m, 5, i64([1, 2])).tolist(), [5, 2])
        with self.assertRaisesRegex(TypeError, "needs an ail_array.Array for a or b"):
            ta.where(m, 1, 2)

    def test_take_put_random_against_lists(self):
        rng = random.Random(4)
        for _ in range(60):
            n = rng.randint(1, 12)
            data = [rng.randint(-50, 50) for _ in range(n)]
            idx = [rng.randint(-n, n - 1) for _ in range(rng.randint(0, 10))]
            a = i64(data)
            self.assertEqual(ta.take(a, i64(idx)).tolist(), [data[i] for i in idx])
            src = [rng.randint(-9, 9) for _ in idx]
            expect = list(data)
            for i, v in zip(idx, src):
                expect[i] = v
            b = a.copy()
            ta.put(b, i64(idx), i64(src))
            self.assertEqual(b.tolist(), expect)
            expect = list(data)
            for i, v in zip(idx, src):
                expect[i] += v
            b = a.copy()
            ta.put(b, i64(idx), i64(src), accumulate=True)
            self.assertEqual(b.tolist(), expect)

    def test_strided_random_against_a_naive_odometer(self):
        rng = random.Random(5)
        for _ in range(80):
            rank = rng.randint(0, 3)
            shape = [rng.randint(0, 3) for _ in range(rank)]
            strides = [rng.randint(-3, 4) for _ in range(rank)]
            offset = rng.randint(0, 20)
            n = 24
            base = ta.array([float(k) for k in range(n)], ta.f64)
            pos = []
            def walk(d, p):
                if d == rank:
                    pos.append(p)
                    return
                for i in range(shape[d]):
                    walk(d + 1, p + i * strides[d])
            walk(0, offset)
            if all(0 <= p < n for p in pos):
                self.assertEqual(ta.gather_strided(base, offset, shape, strides).tolist(), [float(p) for p in pos])
                z = ta.zeros(n, ta.f64)
                ta.scatter_strided(z, offset, shape, strides, ta.array([float(k + 1) for k in range(len(pos))], ta.f64))
                want = [0.0] * n
                for k, p in enumerate(pos):
                    want[p] = float(k + 1)
                self.assertEqual(z.tolist(), want)
            else:
                bad = next(k for k, p in enumerate(pos) if not 0 <= p < n)
                with self.assertRaisesRegex(IndexError, "element %d reads index %d" % (bad, pos[bad])):
                    ta.gather_strided(base, offset, shape, strides)

    def test_segment_sums_use_the_fixed_order_per_segment(self):
        rng = random.Random(6)
        vals = [rng.choice([1e16, 1.0, -1e16, 0.1, 3.0, -0.0]) for _ in range(2500)]
        for dt in (ta.f64, ta.f32):
            a = ta.array(vals, dt)
            offs = [0, 1, 1, 16, 17, 33, 1057, 1058, 2500]
            got = ta.segment_sum(a, i64(offs))
            for k in range(len(offs) - 1):
                self.assertEqual(got.tobytes()[k * dt.itemsize:(k + 1) * dt.itemsize],
                                 ta.array([ta.sum(a[offs[k]:offs[k + 1]])], dt).tobytes(), (dt, k))

    def test_mm_equals_dot_of_row_and_column(self):
        rng = random.Random(7)
        for dt in (ta.f32, ta.f64):
            for m, k, n in ((1, 1, 1), (2, 3, 2), (3, 16, 2), (2, 17, 3), (1, 1025, 2), (2, 2049, 1), (3, 0, 2), (0, 4, 2), (2, 4, 0)):
                av = [rng.choice([1e8, 1.0, -1e8, 0.3, -0.7, 5.5, 0.0, -0.0, 1e-8]) for _ in range(m * k)]
                bv = [rng.choice([1.0, -1.0, 0.1, 3.0, 1e8]) for _ in range(k * n)]
                a, b = ta.array(av, dt), ta.array(bv, dt)
                got = ta.mm(a, b, m, k, n)
                self.assertEqual(len(got), m * n)
                for i in range(m):
                    row = a[i * k:(i + 1) * k]
                    for j in range(n):
                        col = b[j::n]
                        self.assertEqual(got.tobytes()[(i * n + j) * dt.itemsize:(i * n + j + 1) * dt.itemsize],
                                         ta.array([ta.dot(row, col) if k else 0.0], dt).tobytes(), (dt, m, k, n, i, j))

    def test_mm_specials_and_errors(self):
        nan, inf = float("nan"), float("inf")
        got = ta.mm(ta.array([inf, 1.0], ta.f32), ta.array([1.0, -inf], ta.f32), 1, 2, 1)
        self.assertEqual(got.tobytes().hex(), "0000c07f")                  # inf - inf is the canonical NaN
        self.assertEqual(ta.mm(ta.zeros(0, ta.f32), ta.zeros(0, ta.f32), 2, 0, 3).tolist(), [0.0] * 6)
        with self.assertRaisesRegex(ValueError, "a has 3 elements, expected 4 \\(2 x 2\\)"):
            ta.mm(ta.zeros(3, ta.f32), ta.zeros(4, ta.f32), 2, 2, 2)
        with self.assertRaisesRegex(TypeError, "dtypes differ"):
            ta.mm(ta.zeros(4, ta.f32), ta.zeros(4, ta.f64), 2, 2, 2)
        with self.assertRaisesRegex(TypeError, "only f32 and f64"):
            ta.mm(ta.zeros(4, ta.int32), ta.zeros(4, ta.int32), 2, 2, 2)

    def test_promote_properties(self):
        every = list(DT.values())
        for x in every:
            self.assertIs(ta.promote_types(x, x), x)
            for y in every:
                self.assertIs(ta.promote_types(x, y), ta.promote_types(y, x))
        with self.assertRaises(TypeError):
            ta.promote_scalar(ta.f32, "x")


# ---- the 64-bit helpers of the prelude ----------------------------------------------------------------------------
class PreludeHelpers(unittest.TestCase):
    def test_limb_multiply_add_sub_and_checked_ops(self):
        rng = random.Random(1)
        wrap = lambda v: ((v - LO) % (1 << 64)) + LO
        edge = [LO, LO + 1, -(1 << 62), -(1 << 32) - 1, -(1 << 32), -3037000500, -2, -1, 0, 1, 2, 3037000500, 1 << 32, (1 << 32) + 1,
                1 << 62, HI - 1, HI]
        vals = edge + [rng.randint(LO, HI) for _ in range(120)] + [rng.randint(-(1 << 40), 1 << 40) for _ in range(40)]
        for x in vals:
            for y in edge + vals[:30]:
                self.assertEqual(P._ail_tal_wmul(x, y), wrap(x * y), (x, y))
                self.assertEqual(P._ail_tal_wadd(x, y), wrap(x + y), (x, y))
                self.assertEqual(P._ail_tal_wsub(x, y), wrap(x - y), (x, y))
                for op, f in ((0, lambda a, b: a + b), (1, lambda a, b: a - b), (2, lambda a, b: a * b)):
                    e = f(x, y)
                    if LO <= e <= HI:
                        self.assertEqual(P._ail_tal_one(x, y, op, 0), e)
                    else:
                        with self.assertRaises(OverflowError):
                            P._ail_tal_one(x, y, op, 0)
                if y != 0:
                    for op, f in ((3, lambda a, b: a // b), (4, lambda a, b: a % b)):
                        e = f(x, y)
                        if LO <= e <= HI:
                            self.assertEqual(P._ail_tal_one(x, y, op, 0), e)
                        else:
                            with self.assertRaises(OverflowError):
                                P._ail_tal_one(x, y, op, 0)

    def test_exact_and_wrapping_sums(self):
        rng = random.Random(2)
        pool = [LO, HI, -1, 1, 1 << 62, -(1 << 62), 0, 5, rng.randint(LO, HI)]
        for _ in range(300):
            xs = [rng.choice(pool) for _ in range(rng.randint(0, 20))]
            arr = P._AilTAL(len(xs))
            arr.d = list(xs)
            t = sum(xs)
            self.assertEqual(P._ail_tal_wsum(arr), ((t - LO) % (1 << 64)) + LO)
            if LO <= t <= HI:
                self.assertEqual(P._ail_tal_sum(arr), t)
            else:
                with self.assertRaises(OverflowError):
                    P._ail_tal_sum(arr)

    def test_positions_equal_the_reference(self):
        rng = random.Random(8)
        for _ in range(300):
            rank = rng.randint(0, 3)
            shape = [rng.randint(0, 3) for _ in range(rank)]
            strides = [rng.randint(-3, 4) for _ in range(rank)]
            off, n = rng.randint(-2, 20), 24
            try:
                want = ta._positions(n, off, shape, strides, "gather_strided", "reads")
            except IndexError as exc:
                with self.assertRaises(IndexError) as cm:
                    P._ail_ta_positions(n, off, shape, strides, "gather_strided", "reads")
                self.assertEqual(str(cm.exception), str(exc))
                continue
            self.assertEqual(P._ail_ta_positions(n, off, shape, strides, "gather_strided", "reads"), want)

    def test_float_to_int64_equals_the_reference(self):
        rng = random.Random(11)
        xs = [0.0, -0.0, 0.5, -0.5, 1.5, -1.5, 2.5, 4503599627370495.5, -4503599627370495.5, 9.2e18, -9.2e18, 1e300]
        xs += [rng.uniform(-1e19, 1e19) for _ in range(200)] + [rng.uniform(-5, 5) for _ in range(100)]
        for nearest in (False, True):
            for mode in (0, 1):
                for x in xs:
                    a = P._AilTAF(1)
                    a.d = [x]
                    ref = ta.array([x], ta.f64)
                    try:
                        want = ref.astype(ta.int64, "nearest" if nearest else "trunc", "saturate" if mode else "raise").tolist()
                    except OverflowError as exc:
                        with self.assertRaises(OverflowError) as cm:
                            P._ail_taf_to_i64(a, nearest, mode)
                        self.assertEqual(str(cm.exception), str(exc))
                        continue
                    self.assertEqual(P._ail_taf_to_i64(a, nearest, mode).d, want, (x, nearest, mode))


def lowered(source):
    notes = []
    out = ailarray.rewrite_text(source, notes)
    return out, notes


# ---- the program generated from the oracle data ---------------------------------------------------------------------
def flit(x):
    """Source text of a float, specials included."""
    if x != x:
        return "float('nan')"
    if math.isinf(x):
        return "float('inf')" if x > 0 else "(-float('inf'))"
    return repr(x)


def flist(hs, dt=ta.f64):
    return "[" + ", ".join(flit(fl(dt, h)) for h in hs) + "]"


def _pairs(op):
    rows = [r for r in ORACLE["int64_binary"] if r[0] == op]
    return rows


def oracle_program():
    """A program over the oracle's inputs, and the lines PyTorch's outputs say it must print."""
    src = ["import ail_array as ta", "", "",
           "def hx(a: ta.Array[ta.f64]) -> str:", "    return a.tobytes().hex()", "", "",
           "def one_sided(label: str, a: ta.Array[ta.int64], b: ta.Array[ta.int64], op: int):",
           "    for k in range(len(a)):",
           "        try:",
           "            if op == 0:", "                r = a[k:k + 1] + b[k:k + 1]",
           "            elif op == 1:", "                r = a[k:k + 1] - b[k:k + 1]",
           "            elif op == 2:", "                r = a[k:k + 1] * b[k:k + 1]",
           "            elif op == 3:", "                r = a[k:k + 1] // b[k:k + 1]",
           "            else:", "                r = a[k:k + 1] % b[k:k + 1]",
           "            print(label, k, r[0])",
           "        except OverflowError:",
           "            print(label, k, 'overflow')", "", "",
           "def main():"]
    want = []
    for op, name in enumerate(("add", "sub", "mul", "floordiv", "mod")):
        rows = _pairs(name)
        src.append("    a_%s = ta.array(%r, ta.int64)" % (name, [r[1] for r in rows]))
        src.append("    b_%s = ta.array(%r, ta.int64)" % (name, [r[2] for r in rows]))
        wrapped = {"add": "ta.wrapping_add", "sub": "ta.wrapping_sub", "mul": "ta.wrapping_mul", "floordiv": "ta.wrapping_floordiv"}
        if name in wrapped:
            src.append("    print('w%s', %s(a_%s, b_%s).tolist())" % (name, wrapped[name], name, name))
            want.append("w%s %s" % (name, [r[3] for r in rows]))
        src.append("    one_sided('%s', a_%s, b_%s, %d)" % (name, name, name, op))
        for k, r in enumerate(rows):
            exact = {"add": lambda: r[1] + r[2], "sub": lambda: r[1] - r[2], "mul": lambda: r[1] * r[2],
                     "floordiv": lambda: r[1] // r[2], "mod": lambda: r[1] % r[2]}[name]()
            want.append("%s %d %s" % (name, k, r[3] if LO <= exact <= HI else "overflow"))
    un = ORACLE["int64_unary"]
    src.append("    u = ta.array(%r, ta.int64)" % sorted({r[1] for r in un}))
    src.append("    print('wneg', ta.wrapping_neg(u).tolist())")
    src.append("    print('wabs', ta.wrapping_abs(u).tolist())")
    keys = sorted({r[1] for r in un})
    want.append("wneg %s" % [next(r[2] for r in un if r[0] == "neg" and r[1] == a) for a in keys])
    want.append("wabs %s" % [next(r[2] for r in un if r[0] == "abs" and r[1] == a) for a in keys])
    for i, c in enumerate(ORACLE["int64_sums"]):
        src.append("    s%d = ta.array(%r, ta.int64)" % (i, c["values"]))
        src.append("    t%d = ta.array(%r, ta.int64)" % (i, c["other"]))
        src.append("    print('wsum', %d, ta.wrapping_sum(s%d), ta.wrapping_dot(s%d, t%d))" % (i, i, i, i))
        want.append("wsum %d %d %d" % (i, c["sum"], c["dot"]))
        exact = sum(c["values"])
        src.append("    try:\n        print('sum', %d, ta.sum(s%d))\n    except OverflowError:\n        print('sum', %d, 'overflow')" % (i, i, i))
        want.append("sum %d %s" % (i, exact if LO <= exact <= HI else "overflow"))
    # comparisons: f32 special values are exact doubles; int64 rows
    row = ORACLE["compare_f32"][0]
    src.append("    fa = ta.array(%s, ta.f64)" % flist(row["a"], ta.f32))
    src.append("    fb = ta.array(%s, ta.f64)" % flist(row["b"], ta.f32))
    for r in ORACLE["compare_f32"]:
        src.append("    print('f_%s', ta.%s(fa, fb).tolist())" % (r["op"], r["op"]))
        want.append("f_%s %s" % (r["op"], r["array"]))
    for r in ORACLE["compare_int64"]:
        src.append("    print('i_%s', ta.%s(ta.array(%r, ta.int64), ta.array(%r, ta.int64)).tolist(), ta.%s(ta.array(%r, ta.int64), %d).tolist())"
                   % (r["op"], r["op"], r["a"], r["b"], r["op"], r["a"], r["scalar"]))
        want.append("i_%s %s %s" % (r["op"], r["result"], r["scalar_result"]))
    # bool logic
    o = ORACLE["bool"]
    src.append("    ba = ta.array(%r, ta.bool_)" % o["a"])
    src.append("    bb = ta.array(%r, ta.bool_)" % o["b"])
    for nm, key in (("and", "and"), ("or", "or"), ("xor", "xor")):
        src.append("    print('b_%s', ta.logical_%s(ba, bb).tolist())" % (nm, nm))
        want.append("b_%s %s" % (nm, o[key]))
    src.append("    print('b_not', ta.logical_not(ba).tolist())")
    want.append("b_not %s" % o["not"])
    src.append("    print('b_sum', ta.sum(ba), ta.any(ba), ta.all(ba), ta.any(ta.zeros(0, ta.bool_)), ta.all(ta.zeros(0, ta.bool_)))")
    want.append("b_sum %s %s %s %s %s" % (o["sum"], o["any"][0], o["all"][0], o["any"][2], o["all"][2]))
    # casts that the lowering builds: int64 -> f64 / int32 wrap / bool, f64 -> bool, f64 -> int64
    c = ORACLE["casts"]
    src.append("    ints = ta.array(%r, ta.int64)" % c["ints"])
    src.append("    print('c_f64', hx(ints.astype(ta.f64)))")
    want.append("c_f64 %s" % "".join(c["to_f64"]))
    src.append("    print('c_i32', ints.astype(ta.int32, 'trunc', 'wrap').tolist())")
    want.append("c_i32 %s" % c["to_int32"])
    src.append("    print('c_bool', ints.astype(ta.bool_).tolist())")
    want.append("c_bool %s" % c["to_bool"])
    src.append("    fs = ta.array(%s, ta.f64)" % flist(c["floats"]))
    src.append("    print('c_fbool', fs.astype(ta.bool_).tolist())")
    want.append("c_fbool %s" % c["f64_to_bool"])
    src.append("    inr = ta.array(%s, ta.f64)" % flist(c["f64_in_range"]))
    src.append("    print('c_trunc', inr.astype(ta.int64).tolist())")
    want.append("c_trunc %s" % c["f64_to_int64_trunc"])
    # take / put (f32 values are exact doubles)
    tk = ORACLE["take"]
    src.append("    x = ta.array(%s, ta.f64)" % flist(tk["x"], ta.f32))
    for i, case in enumerate(tk["cases"]):
        src.append("    try:\n        print('take', %d, hx(ta.take(x, ta.array(%r, ta.int64))))\n    except IndexError as exc:\n        print('take', %d, exc)"
                   % (i, case["idx"], i))
        if "error" in case:
            want.append("take %d %s" % (i, case["error"][1]))
        else:
            want.append("take %d %s" % (i, "".join(struct.pack("<d", fl(ta.f32, h)).hex() for h in case["result"])))
    for i, case in enumerate(ORACLE["put"]["cases"]):
        src.append("    y = x.copy()")
        src.append("    try:\n        ta.put(y, ta.array(%r, ta.int64), ta.array(%r, ta.f64), accumulate=%r)\n    except IndexError as exc:\n        print('put', %d, exc)"
                   % (case["idx"], case["src"], case["accumulate"], i))
        src.append("    print('put', %d, hx(y))" % i)
        if "error" in case:
            want.append("put %d %s" % (i, case["error"][1]))
        res = case.get("result", case.get("after"))
        want.append("put %d %s" % (i, "".join(struct.pack("<d", fl(ta.f32, h)).hex() for h in res)))
    # strided gather / scatter
    g = ORACLE["gather_strided"]
    src.append("    base = ta.array(%s, ta.f64)" % flist(g["base"]))
    for i, case in enumerate(g["cases"]):
        src.append("    try:\n        print('gather', %d, hx(ta.gather_strided(base, %d, %r, %r)))\n    except IndexError:\n        print('gather', %d, 'IndexError')"
                   % (i, case["offset"], case["shape"], case["strides"], i))
        want.append("gather %d %s" % (i, "".join(case["result"]) if "result" in case else "IndexError"))
    for i, case in enumerate(ORACLE["scatter_strided"]["cases"]):
        src.append("    z = ta.zeros(24, ta.f64)")
        src.append("    zsrc = ta.array(%s, ta.f64)" % flist(case["src"]))
        src.append("    try:\n        ta.scatter_strided(z, %d, %r, %r, zsrc)\n    except IndexError:\n        print('scatter', %d, 'IndexError')"
                   % (case["offset"], case["shape"], case["strides"], i))
        src.append("    print('scatter', %d, hx(z))" % i)
        if "result" not in case:
            want.append("scatter %d IndexError" % i)
        want.append("scatter %d %s" % (i, "".join(case["result"]) if "result" in case else "00" * 192))
    # segments (small ints: every order gives the same sum)
    s = ORACLE["segments"]
    src.append("    sv = ta.array(%s, ta.f64)" % flist(s["values"], ta.f32))
    src.append("    so = ta.array(%r, ta.int64)" % s["offsets"])
    src.append("    print('seg_sum', hx(ta.segment_sum(sv, so)))")
    want.append("seg_sum %s" % "".join(struct.pack("<d", fl(ta.f32, h)).hex() for h in s["sum_f32"]))
    src.append("    sn = ta.array(%r, ta.int64)" % s["int_values"])
    src.append("    print('seg_isum', ta.wrapping_segment_sum(sn, so).tolist())")
    want.append("seg_isum %s" % s["sum_int64"])
    src.append("    ne = ta.array([0, 3, 7, 10], ta.int64)")
    src.append("    print('seg_max', hx(ta.segment_max(sv, ne)), hx(ta.segment_min(sv, ne)), ta.segment_argmax(sv, ne).tolist(), ta.segment_argmin(sv, ne).tolist())")
    pk = lambda hs: "".join(struct.pack("<d", fl(ta.f32, h)).hex() for h in hs if h is not None)
    want.append("seg_max %s %s %s %s" % (pk(s["max"]), pk(s["min"]), [x for x in s["argmax"] if x is not None],
                                         [x for x in s["argmin"] if x is not None]))
    nv = s["nan"]
    src.append("    sx = ta.array(%s, ta.f64)" % flist(nv["values"], ta.f32))
    src.append("    z2 = ta.array([0, 5], ta.int64)")
    src.append("    print('seg_nan', hx(ta.segment_max(sx, z2)), hx(ta.segment_min(sx, z2)), ta.segment_argmax(sx, z2).tolist(), ta.segment_argmin(sx, z2).tolist())")
    want.append("seg_nan %s %s [%d] [%d]" % (pk([nv["max"]]), pk([nv["min"]]), nv["argmax"], nv["argmin"]))
    src.append("")
    src.append("")
    src.append("main()")
    return "\n".join(src) + "\n", want


ORACLE_SOURCE, ORACLE_WANT = oracle_program()


def oracle_expected_stdout():
    # canonical NaN: struct packs a NaN float as 7ff8000000000000
    return "".join(line + "\n" for line in ORACLE_WANT)


def run_py(directory, name):
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")
    env.pop("PYTHONPATH", None)
    return subprocess.run([sys.executable, "-B", name], cwd=directory, capture_output=True, text=True, timeout=600, env=env)


class WhiteBox(unittest.TestCase):
    def check(self, name, source):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            (tmp / "ref").mkdir()
            shutil.copy(ROOT / "ail_array.py", tmp / "ref" / "ail_array.py")
            (tmp / "ref" / "prog.py").write_text(source, encoding="utf-8")
            text, notes = lowered(source)
            self.assertEqual(notes, [])
            self.assertNotEqual(text, source)
            self.assertNotIn("import ail_array", text)
            (tmp / "low").mkdir()
            (tmp / "low" / "prog.py").write_text(text, encoding="utf-8")
            ref, low = run_py(tmp / "ref", "prog.py"), run_py(tmp / "low", "prog.py")
            self.assertEqual(ref.returncode, 0, ref.stderr[-500:])
            self.assertEqual(low.stdout, ref.stdout)
            self.assertEqual(low.returncode, ref.returncode)
            return ref.stdout

    def test_cases_lowered_text_equals_reference(self):
        for name in NAMES:
            with self.subTest(case=name):
                self.check(name, (CASES / (name + ".py")).read_text(encoding="utf-8"))

    def test_oracle_program_reference_and_lowered_print_what_torch_computed(self):
        out = self.check("oracle", ORACLE_SOURCE)
        self.assertEqual(out, oracle_expected_stdout())

    def test_programs_without_the_new_names_keep_their_text(self):
        src = "import ail_array as ta\n\ndef main():\n    a = ta.array([1.0, 2.0], ta.f64)\n    b = ta.array([1, 2], ta.int32)\n    print(a * a + a, b + b, ta.sum(a))\n\nmain()\n"
        text, notes = lowered(src)
        self.assertEqual(notes, [])
        self.assertNotIn("_AilTAL", text)
        self.assertNotIn("_AilTAO", text)
        self.assertNotIn("_ail_tal_", text)


REFUSED = [
    ("mm", "import ail_array as ta\na = ta.zeros(4, ta.f64)\nb = ta.mm(a, a, 2, 2, 2)\n", "T6"),
    ("promote_types", "import ail_array as ta\nx = ta.promote_types(ta.f64, ta.int64)\n", "typed path"),
    ("promote_scalar", "import ail_array as ta\nx = ta.promote_scalar(ta.f64, 1)\n", "typed path"),
    ("exact int64 dot", "import ail_array as ta\na = ta.zeros(3, ta.int64)\nb = ta.dot(a, a)\n", "wrapping_dot"),
    ("accumulate on bool", "import ail_array as ta\na = ta.zeros(3, ta.bool_)\ni = ta.zeros(1, ta.int64)\nta.put(a, i, True, accumulate=True)\n", "bool_"),
    ("put overflow text", "import ail_array as ta\na = ta.zeros(3, ta.int64)\ni = ta.zeros(1, ta.int64)\nta.put(a, i, 1, accumulate=True, overflow='clamp')\n", "overflow"),
    ("take with a list", "import ail_array as ta\na = ta.zeros(3, ta.f64)\nb = ta.take(a, [0, 1])\n", "indices"),
    ("gather shape not ints", "import ail_array as ta\na = ta.zeros(3, ta.f64)\nb = ta.gather_strided(a, 0, (1.5,), (1,))\n", "int"),
    ("gather without strides", "import ail_array as ta\na = ta.zeros(3, ta.f64)\nb = ta.gather_strided(a, 0, (1,))\n", "strides"),
    ("where without arrays", "import ail_array as ta\nm = ta.zeros(3, ta.bool_)\nb = ta.where(m, 1, 2)\n", "operand"),
    ("fancy indexing", "import ail_array as ta\na = ta.zeros(3, ta.int64)\nb = a[[0, 2]]\n", "ta.take"),
    ("comparison operator", "import ail_array as ta\na = ta.zeros(3, ta.int64)\nb = a < a\n", "write instead"),
    ("int8 still later", "import ail_array as ta\na = ta.zeros(3, ta.int8)\n", "stage T3"),
    ("f32 still later", "import ail_array as ta\na = ta.zeros(3, ta.f32)\n", "stage T3"),
    ("int16", "import ail_array as ta\na = ta.zeros(3, ta.int16)\n", "has f64, f32, f16, int8, int32, int64, bool_"),
    ("int64 truediv", "import ail_array as ta\na = ta.zeros(3, ta.int64)\nb = a / 2\n", "astype"),
    ("bool pow", "import ail_array as ta\na = ta.zeros(3, ta.bool_)\nb = a ** 2\n", "write instead"),
    ("param dtypes mixed", "import ail_array as ta\ndef f(a):\n    return a\nf(ta.zeros(1, ta.int64))\nf(ta.zeros(1, ta.bool_))\n", "annotate"),
    ("segment offsets list", "import ail_array as ta\na = ta.zeros(3, ta.f64)\nb = ta.segment_sum(a, [0, 3])\n", "known dtype"),
]


class Refusals(unittest.TestCase):
    def test_each_refusal_has_a_line_and_a_hint(self):
        for name, src, needle in REFUSED:
            with self.subTest(case=name):
                text, notes = lowered(src)
                self.assertEqual(text, src, "a refused program is left as written")
                self.assertTrue(notes, "no refusal for %s" % name)
                line, why = notes[0]
                self.assertGreaterEqual(line, 1)
                self.assertIn(needle, why)

    def test_the_new_dtypes_are_not_refused(self):
        for dt in ("int64", "bool_"):
            text, notes = lowered("import ail_array as ta\na = ta.zeros(3, ta.%s)\nprint(a)\n" % dt)
            self.assertEqual(notes, [])
            self.assertIn("_ail_ta%s_zeros" % ("l" if dt == "int64" else "o"), text)


@unittest.skipUnless(CC, "installed C compiler required")
class Native(unittest.TestCase):
    """Built programs print what CPython prints with the reference beside the program, and what PyTorch computed."""

    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory(prefix="ail-array-t3b-")
        cls.dir = Path(cls.tmp.name)
        sources = {n: (CASES / (n + ".py")).read_text(encoding="utf-8") for n in NAMES}
        sources["oracle"] = ORACLE_SOURCE
        cls.sources = sources
        cls.ref = {}
        for name, src in sources.items():
            d = cls.dir / name / "ref"
            d.mkdir(parents=True)
            shutil.copy(ROOT / "ail_array.py", d)
            (d / "prog.py").write_text(src, encoding="utf-8")
            cls.ref[name] = run_py(d, "prog.py")

        def build(job):
            name, mode = job
            d = cls.dir / name / mode
            d.mkdir(parents=True)
            (d / "prog.py").write_text(sources[name], encoding="utf-8")
            env = dict(os.environ, PYTHONPATH=str(ROOT))
            for key in ("AIL_UNIFIED_FORCE", "AIL_NO_GENERAL"):
                env.pop(key, None)
            if mode == "forced":
                env["AIL_UNIFIED_FORCE"] = "1"
            if mode == "typed":
                env["AIL_NO_GENERAL"] = "1"
            done = subprocess.run([sys.executable, "-B", str(ROOT / "ail_chatgpt.py"), "compile", "prog.py", "-o", "prog.out"],
                                  cwd=d, capture_output=True, text=True, timeout=1200, env=env)
            run = None
            if done.returncode == 0:
                run = subprocess.run([str(d / "prog.out")], capture_output=True, text=True, timeout=300)
            return job, done, run

        jobs = [(n, m) for n in sources for m in ("default", "forced")] + [("typed64", "typed")]
        with ThreadPoolExecutor(max_workers=2) as pool:
            cls.out = dict(pool.map(lambda j: (j, build(j)), jobs))

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def check(self, name, mode):
        job, done, run = self.out[(name, mode)]
        self.assertEqual(done.returncode, 0, (done.stdout + done.stderr)[-1500:])
        ref = self.ref[name]
        self.assertEqual(ref.returncode, 0, ref.stderr[-500:])
        self.assertEqual(run.stdout, ref.stdout)
        self.assertEqual(run.returncode, ref.returncode)
        if name == "oracle":
            self.assertEqual(run.stdout, oracle_expected_stdout())


def _add(name, mode):
    setattr(Native, "test_%s_%s" % (name, mode), lambda self: self.check(name, mode))


for _n in NAMES + ["oracle"]:
    for _m in ("default", "forced"):
        _add(_n, _m)
_add("typed64", "typed")


if __name__ == "__main__":
    unittest.main()
