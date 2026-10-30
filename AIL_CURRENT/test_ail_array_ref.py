"""Stage T1 of docs/design/TYPED_ARRAY.md: the pure-Python reference `ail_array.py`, checked on CPython only.

The reference is the oracle for AIL's native lowering, so it gets its own oracle here, written independently:
* float rounding: exact `fractions.Fraction` results rounded to bits with integer code (ties to even, subnormals,
  overflow, signed zeros, IEEE special values), never through `struct`;
* ints: Python's exact ints and independent wrap/saturate formulas;
* the fixed sum order: a second implementation written from the text of design 3.5, plus simulations of SIMD widths
  4/8/16 and of 1..8 threads that split the block tree, all of which must give the same bits.
No AIL compiler is involved; nothing is compiled.
"""
import builtins
import math
from fractions import Fraction
from pathlib import Path
import random
import struct
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import ail_array as ta  # noqa: E402

FMT = {  # dtype -> (precision p, min normal exponent, max exponent, exponent bits, total bits)
    ta.f16: (11, -14, 15, 5, 16),
    ta.f32: (24, -126, 127, 8, 32),
    ta.f64: (53, -1022, 1023, 11, 64),
}
CANON = {ta.f16: 0x7e00, ta.f32: 0x7fc00000, ta.f64: 0x7ff8000000000000}
FLOATS = (ta.f16, ta.f32, ta.f64)
INTS = (ta.int8, ta.int32)


# ---- the independent oracle -----------------------------------------------------------------------------------------
def bits_of(dt, x):
    """Bits of a Python float that is exactly a value of `dt` (no rounding happens here)."""
    return int.from_bytes(struct.pack('<' + dt.code, x), 'little')


def value_of(dt, b):
    return struct.unpack('<' + dt.code, b.to_bytes(dt.itemsize, 'little'))[0]


def inf_bits(dt, neg):
    p, _, _, eb, total = FMT[dt]
    return (int(neg) << (total - 1)) | (((1 << eb) - 1) << (p - 1))


def floor_log2(q):
    e = q.numerator.bit_length() - q.denominator.bit_length()
    while Fraction(2) ** e > q:
        e -= 1
    while Fraction(2) ** (e + 1) <= q:
        e += 1
    return e


def round_bits(dt, q, neg):
    """Bits of the exact magnitude `q` (a Fraction >= 0) with sign `neg`, rounded to nearest-even in `dt`."""
    p, emin, emax, _, total = FMT[dt]
    sign = int(neg) << (total - 1)
    if q == 0:
        return sign
    e = builtins.max(floor_log2(q), emin)
    m = q * Fraction(2) ** (p - 1 - e)
    fl = m.numerator // m.denominator
    rem = m - fl
    if rem > Fraction(1, 2) or (rem == Fraction(1, 2) and fl % 2):
        fl += 1
    if fl == 1 << p:
        fl >>= 1
        e += 1
    if e > emax:
        return inf_bits(dt, neg)
    if fl < 1 << (p - 1):
        return sign | fl
    return sign | ((e + emax) << (p - 1)) | (fl - (1 << (p - 1)))


def sqrt_bits(dt, x):
    """Correctly rounded sqrt of a finite x >= 0 by integer square roots (exact ties cannot occur for sqrt)."""
    p, emin, _, _, _ = FMT[dt]
    q = Fraction(x)
    if q == 0:
        return bits_of(dt, x)
    e = builtins.max(floor_log2(q) // 2, emin)
    k = p - 1 - e
    n = q * Fraction(4) ** k
    if n.denominator != 1:
        whole = n.numerator // n.denominator
        exact = False
    else:
        whole = n.numerator
        exact = True
    fl = math.isqrt(whole)
    exact = exact and fl * fl == whole
    # round half up is enough: sqrt is never exactly halfway between two representable values
    if not exact and 4 * n > (2 * fl + 1) ** 2:
        fl += 1
    return round_bits(dt, Fraction(fl) / Fraction(2) ** k, False)


def neg_zero(x):
    return x == 0 and math.copysign(1.0, x) < 0


def expected_op(dt, op, x, y):
    """Bits the module must give for `x op y` (x, y values of dt), by the IEEE rules and the exact oracle."""
    if x != x or (y is not None and y != y):
        return CANON[dt]
    if op == 'sqrt':
        if x < 0:
            return CANON[dt]
        if math.isinf(x):
            return inf_bits(dt, False)
        return sqrt_bits(dt, x)
    if op == '-':
        op, y = '+', -y
    sx, sy = math.copysign(1.0, x) < 0, math.copysign(1.0, y) < 0
    if op == '+':
        if math.isinf(x) or math.isinf(y):
            if math.isinf(x) and math.isinf(y) and sx != sy:
                return CANON[dt]
            return inf_bits(dt, sx if math.isinf(x) else sy)
        q = Fraction(x) + Fraction(y)
        if q == 0:
            return round_bits(dt, Fraction(0), sx and sy)
        return round_bits(dt, abs(q), q < 0)
    neg = sx != sy
    if op == '*':
        if math.isinf(x) or math.isinf(y):
            if x == 0 or y == 0:
                return CANON[dt]
            return inf_bits(dt, neg)
        return round_bits(dt, abs(Fraction(x) * Fraction(y)), neg)
    if op == '/':
        if math.isinf(x):
            return CANON[dt] if math.isinf(y) else inf_bits(dt, neg)
        if math.isinf(y):
            return round_bits(dt, Fraction(0), neg)
        if y == 0:
            return CANON[dt] if x == 0 else inf_bits(dt, neg)
        return round_bits(dt, abs(Fraction(x) / Fraction(y)), neg)
    raise AssertionError(op)


def edge_values(dt):
    p, emin, emax, _, _ = FMT[dt]
    tiny = 2.0 ** (emin - p + 1)
    big = (2.0 - 2.0 ** (1 - p)) * 2.0 ** emax
    ulp1 = 2.0 ** (1 - p)
    vals = [0.0, tiny, 2 * tiny, 3 * tiny, 2.0 ** emin - tiny, 2.0 ** emin, big, big / 2, 1.0, 1.0 + ulp1,
            1.0 - ulp1 / 2, 1.5, 2.0, 3.0, 0.5, 0.1, 1 / 3, 7.0, 1000.0, float('inf')]
    vals = [ta.array([v], dt)[0] for v in vals]
    out = []
    for v in vals:
        out += [v, -v]
    return out + [float('nan')]


def random_values(dt, n, rng):
    out = []
    for _ in range(n):
        out.append(value_of(dt, rng.getrandbits(dt.itemsize * 8)))
    return out


def array_bits(a):
    size = a.dtype.itemsize
    raw = a.tobytes()
    return [int.from_bytes(raw[k:k + size], 'little') for k in range(0, len(raw), size)]


def fixed_order_sum(xs, A):
    """A second implementation of design 3.5, written from the text, not from ail_array."""
    def r(v):
        return value_of(A, round_bits_any(A, v))

    def block(part):
        lanes = []
        for lane in range(16):
            acc = -0.0
            for v in part[lane::16]:
                acc = r(acc + v)
            lanes.append(acc)
        for w in (8, 4, 2, 1):
            lanes = [r(lanes[i] + lanes[i + w]) for i in range(w)] + lanes[w:]
        return lanes[0]

    def combine(bs):
        if len(bs) == 1:
            return bs[0]
        p = 1 << ((len(bs) - 1).bit_length() - 1)
        return r(combine(bs[:p]) + combine(bs[p:]))

    if not xs:
        return 0.0
    out = combine([block(xs[s:s + 1024]) for s in range(0, len(xs), 1024)])
    return float('nan') if out != out else out


def round_bits_any(dt, v):
    """Oracle rounding of any Python float (incl. inf and NaN) to dt."""
    if v != v:
        return CANON[dt]
    if math.isinf(v):
        return inf_bits(dt, v < 0)
    return round_bits(dt, abs(Fraction(v)), math.copysign(1.0, v) < 0)


def simulated_sum(xs, A, width, threads):
    """The same order computed the way native code will: vector registers of `width` lanes (width divides 16) and
    `threads` workers that each take a subtree of the block tree. Must give the bits of the definition."""
    def r(v):
        return value_of(A, round_bits_any(A, v))

    def block(s, e):
        regs = [[-0.0] * width for _ in range(16 // width)]
        for row in range(s, e, 16):
            for j in range(16 // width):
                for lane in range(width):
                    k = row + j * width + lane
                    if k < e:
                        regs[j][lane] = r(regs[j][lane] + xs[k])
        lanes = [v for reg in regs for v in reg]
        w = 8
        while w:
            for i in range(w):
                lanes[i] = r(lanes[i] + lanes[i + w])
            w //= 2
        return lanes[0]

    n = len(xs)
    if not n:
        return 0.0
    starts = list(range(0, n, 1024))

    def split(lo, hi, workers):
        # one worker computes the subtree [lo, hi) alone; more workers split it at the tree's own split point
        if workers == 1 or hi - lo == 1:
            return ('leaf', lo, hi)
        p = 1
        while p * 2 < hi - lo:
            p *= 2
        left = builtins.max(1, workers // 2)
        return ('node', split(lo, lo + p, left), split(lo + p, hi, workers - left))

    def alone(lo, hi):
        if hi - lo == 1:
            return block(starts[lo], builtins.min(starts[lo] + 1024, n))
        p = 1
        while p * 2 < hi - lo:
            p *= 2
        return r(alone(lo, lo + p) + alone(lo + p, hi))

    def run(plan):
        if plan[0] == 'leaf':
            return alone(plan[1], plan[2])
        return r(run(plan[1]) + run(plan[2]))

    out = run(split(0, len(starts), threads))
    return float('nan') if out != out else out


# ---- tests ---------------------------------------------------------------------------------------------------------
class Rounding(unittest.TestCase):
    """Stores and casts of binary64 values into f32/f16 against the Fraction oracle."""

    def check_store(self, dt, values):
        got = array_bits(ta.array(values, dt))
        for v, g in zip(values, got):
            self.assertEqual(g, round_bits_any(dt, v), '%s store of %r' % (dt, v))

    def test_every_f16_tie_and_neighbours(self):
        # exhaustive: every midpoint between adjacent positive f16 values (ties go to even), and its two neighbours
        values = []
        for b in range(0x7c00):
            lo, hi = value_of(ta.f16, b), value_of(ta.f16, b + 1)
            mid = (lo + hi) / 2
            values += [mid, -mid, math.nextafter(mid, 0.0), math.nextafter(mid, math.inf)]
        self.check_store(ta.f16, values)

    def test_f32_ties_sampled(self):
        rng = random.Random(32)
        values = []
        for _ in range(20000):
            b = rng.randrange(0x7f800000)
            lo, hi = value_of(ta.f32, b), value_of(ta.f32, b + 1)
            mid = (lo + hi) / 2
            values += [mid, math.nextafter(mid, 0.0), math.nextafter(mid, math.inf)]
        self.check_store(ta.f32, values)

    def test_boundaries(self):
        f32max = value_of(ta.f32, 0x7f7fffff)
        f16max = 65504.0
        values = [f32max, math.nextafter(2.0 ** 128 - 2.0 ** 103, 0), 2.0 ** 128 - 2.0 ** 103, 2.0 ** 128, 1e300,
                  -1e300, f16max, 65519.99999999999, 65520.0, 2.0 ** -149, 2.0 ** -150, 3 * 2.0 ** -151,
                  2.0 ** -24, 2.0 ** -25, 1.5 * 2.0 ** -24, 2.5 * 2.0 ** -24, 5e-324, -0.0, 0.0, math.inf, -math.inf]
        for dt in (ta.f32, ta.f16):
            self.check_store(dt, values)
        self.assertEqual(array_bits(ta.array([65520.0, -65520.0], ta.f16)), [0x7c00, 0xfc00])
        self.assertEqual(array_bits(ta.array([2.0 ** -25, 3 * 2.0 ** -25], ta.f16)), [0, 2])
        self.assertEqual(array_bits(ta.array([-0.0], ta.f16)), [0x8000])

    def test_random_binary64_values(self):
        rng = random.Random(7)
        values = [math.ldexp(rng.random() + 0.5, rng.randrange(-160, 140)) * rng.choice((1, -1)) for _ in range(20000)]
        for dt in (ta.f32, ta.f16):
            self.check_store(dt, values)

    def test_ints_into_float_arrays(self):
        values = [0, 1, -1, 2 ** 24 + 1, 2 ** 24 + 3, 2 ** 31 - 1, -2 ** 31, 2049, 65519, 65520, 10 ** 30, True]
        for dt in FLOATS:
            got = array_bits(ta.array(values, dt))
            self.assertEqual(got, [round_bits_any(dt, float(v)) for v in values])
        with self.assertRaisesRegex(OverflowError, 'int too large to convert to float'):
            ta.array([10 ** 400], ta.f32)


class FloatOps(unittest.TestCase):
    """+ - * / and sqrt in each float dtype against the exact oracle (random bit patterns and the edge set)."""

    def check(self, dt, xs, ys):
        a, b = ta.array(xs, dt), ta.array(ys, dt)
        xs, ys = a.tolist(), b.tolist()
        for op in '+-*/':
            got = array_bits({'+': a + b, '-': a - b, '*': a * b, '/': a / b}[op])
            for x, y, g in zip(xs, ys, got):
                self.assertEqual(g, expected_op(dt, op, x, y), '%s %r %s %r' % (dt, x, op, y))
        got = array_bits(ta.sqrt(a))
        for x, g in zip(xs, got):
            self.assertEqual(g, expected_op(dt, 'sqrt', x, None), '%s sqrt %r' % (dt, x))

    def test_edges_all_pairs(self):
        for dt in FLOATS:
            e = edge_values(dt)
            self.check(dt, [x for x in e for _ in e], [y for _ in e for y in e])

    def test_random_bit_patterns(self):
        rng = random.Random(11)
        for dt, n in ((ta.f16, 6000), (ta.f32, 4000), (ta.f64, 2000)):
            self.check(dt, random_values(dt, n, rng), random_values(dt, n, rng))

    def test_every_f16_sqrt(self):
        a = ta.frombytes(b''.join(k.to_bytes(2, 'little') for k in range(65536)), ta.f16)
        got = array_bits(ta.sqrt(a))
        for x, g in zip(a.tolist(), got):
            self.assertEqual(g, expected_op(ta.f16, 'sqrt', x, None), repr(x))

    def test_nothing_is_fused(self):
        # a*b + c rounds twice in f32; the single-rounding result differs for these inputs
        a = ta.array([1.0 + 2.0 ** -12], ta.f32)
        c = ta.array([-(1.0 + 2.0 ** -11)], ta.f32)
        two = (a * a + c).tolist()[0]
        self.assertEqual(two, 0.0)
        exact = float(Fraction(a[0]) * Fraction(a[0]) + Fraction(c[0]))
        self.assertNotEqual(two, exact)

    def test_scalars_and_reflected(self):
        a = ta.array([1.0, 3.0, -0.0], ta.f16)
        tenth = value_of(ta.f16, round_bits_any(ta.f16, 0.1))                 # the scalar is stored to f16 first
        self.assertEqual(tenth, 0.0999755859375)
        self.assertEqual(array_bits(a * 0.1), [round_bits_any(ta.f16, tenth * v) for v in (1.0, 3.0, -0.0)])
        self.assertEqual((1.0 - a).tolist(), [0.0, -2.0, 1.0])
        self.assertEqual((2 / a).tolist(), [2.0, value_of(ta.f16, round_bits_any(ta.f16, 2 / 3)), -math.inf])
        self.assertEqual(array_bits(0.0 * ta.array([-1.0], ta.f32)), [0x80000000])
        self.assertEqual(array_bits(-ta.array([0.0, -0.0], ta.f32)), [0x80000000, 0])
        self.assertEqual(array_bits(abs(ta.array([-0.0, -2.0], ta.f32))), [0, 0x40000000])

    def test_ieee_division_and_overflow(self):
        for dt in FLOATS:
            a = ta.array([1.0, -1.0, 0.0, -0.0, math.inf], dt)
            z = ta.zeros(5, dt)
            got = array_bits(a / z)
            self.assertEqual(got, [inf_bits(dt, False), inf_bits(dt, True), CANON[dt], CANON[dt], inf_bits(dt, False)])
            big = ta.full(1, value_of(dt, inf_bits(dt, False) - 1), dt)           # the largest finite value
            self.assertEqual(array_bits(big * 2.0), [inf_bits(dt, False)])
            self.assertEqual(array_bits(-big * 2.0), [inf_bits(dt, True)])

    def test_math_functions(self):
        xs = [0.0, -0.0, 1.0, -1.0, 0.5, 2.0, 10.0, 100.0, 1000.0, -1000.0, math.inf, -math.inf, math.nan, 1e-30]
        for dt in FLOATS:
            a = ta.array(xs, dt)
            vals = a.tolist()
            for fn, ref in ((ta.exp, math.exp), (ta.log, math.log), (ta.tanh, math.tanh)):
                got = array_bits(fn(a))
                for x, g in zip(vals, got):
                    if x != x:
                        want = CANON[dt]
                    elif fn is ta.log and x < 0:
                        want = CANON[dt]
                    elif fn is ta.log and x == 0:
                        want = inf_bits(dt, True)
                    else:
                        try:
                            want = round_bits_any(dt, ref(x))
                        except OverflowError:
                            want = inf_bits(dt, False)
                    self.assertEqual(g, want, '%s %s(%r)' % (dt, fn.__name__, x))
        with self.assertRaises(TypeError):
            ta.sqrt(ta.array([4], ta.int32))


class NaNs(unittest.TestCase):
    def test_produced_nans_are_canonical(self):
        for dt in FLOATS:
            inf = ta.full(3, math.inf, dt)
            self.assertEqual(array_bits(inf - inf), [CANON[dt]] * 3)
            self.assertEqual(array_bits(inf * ta.zeros(3, dt)), [CANON[dt]] * 3)
            self.assertEqual(array_bits(ta.array([math.nan, -math.nan, math.inf - math.inf], dt)), [CANON[dt]] * 3)
            self.assertEqual(array_bits(-ta.array([math.nan], dt)), [CANON[dt]])
            self.assertEqual(array_bits(ta.sqrt(ta.array([-1.0], dt))), [CANON[dt]])
            for other in FLOATS:
                self.assertEqual(array_bits(ta.array([math.nan], dt).astype(other)), [CANON[other]])

    def test_payloads_survive_storage_until_an_op(self):
        raw = (0x7f800001).to_bytes(4, 'little') + (0xffc12345).to_bytes(4, 'little')
        a = ta.frombytes(raw, ta.f32)
        self.assertEqual(a.tobytes(), raw)
        self.assertEqual(a[0:2].tobytes(), raw)
        self.assertEqual(a.copy().tobytes(), raw)
        self.assertEqual(array_bits(a + 1.0), [CANON[ta.f32]] * 2)
        self.assertEqual(array_bits(a.astype(ta.f32)), [CANON[ta.f32]] * 2)
        x = a[0]
        self.assertTrue(x != x)


class IntOps(unittest.TestCase):
    """int8 over every pair, int32 over edges and random pairs; first-index errors; in-place prefixes."""

    def pairs(self, dt):
        if dt is ta.int8:
            vals = list(range(-128, 128))
        else:
            rng = random.Random(5)
            vals = [-2 ** 31, -2 ** 31 + 1, -46341, -46340, -65536, -2, -1, 0, 1, 2, 46340, 46341, 65535, 2 ** 31 - 2,
                    2 ** 31 - 1] + [rng.randrange(-2 ** 31, 2 ** 31) for _ in range(40)]
        return [x for x in vals for _ in vals], [y for _ in vals for y in vals]

    def test_checked_ops(self):
        ops = {'+': (lambda x, y: x + y, 'add'), '-': (lambda x, y: x - y, 'sub'), '*': (lambda x, y: x * y, 'mul'),
               '//': (lambda x, y: x // y, 'floordiv'), '%': (lambda x, y: x % y, 'mod')}
        for dt in INTS:
            xs, ys = self.pairs(dt)
            for sym, (fn, name) in ops.items():
                first = None
                for k, (x, y) in enumerate(zip(xs, ys)):
                    if sym in ('//', '%') and y == 0:
                        first = (ZeroDivisionError, 'integer division or modulo by zero')
                        break
                    if not dt.lo <= fn(x, y) <= dt.hi:
                        first = (OverflowError, '%s %s overflow at index %d' % (dt.name, name, k))
                        break
                a, b = ta.array(xs, dt), ta.array(ys, dt)
                run = {'+': lambda: a + b, '-': lambda: a - b, '*': lambda: a * b, '//': lambda: a // b,
                       '%': lambda: a % b}[sym]
                self.assertIsNotNone(first, sym)
                with self.assertRaises(first[0]) as cm:
                    run()
                self.assertEqual(str(cm.exception), first[1])
                keep = [(x, y) for x, y in zip(xs, ys)
                        if not (sym in ('//', '%') and y == 0) and dt.lo <= fn(x, y) <= dt.hi]
                a, b = ta.array([x for x, _ in keep], dt), ta.array([y for _, y in keep], dt)
                got = {'+': lambda: a + b, '-': lambda: a - b, '*': lambda: a * b, '//': lambda: a // b,
                       '%': lambda: a % b}[sym]().tolist()
                self.assertEqual(got, [fn(x, y) for x, y in keep], '%s %s' % (dt, sym))

    def test_unary(self):
        for dt in INTS:
            a = ta.array([1, dt.lo + 1, dt.hi, dt.lo, 5], dt)
            with self.assertRaisesRegex(OverflowError, r'^%s neg overflow at index 3$' % dt.name):
                -a
            with self.assertRaisesRegex(OverflowError, r'^%s abs overflow at index 3$' % dt.name):
                abs(a)
            b = ta.array([1, dt.lo + 1, dt.hi, 0], dt)
            self.assertEqual((-b).tolist(), [-1, dt.hi, dt.lo + 1, 0])
            self.assertEqual(abs(b).tolist(), [1, dt.hi, dt.hi, 0])

    def test_wrapping_and_saturating(self):
        for dt in INTS:
            xs, ys = self.pairs(dt)
            a, b = ta.array(xs, dt), ta.array(ys, dt)
            m = 1 << dt.bits

            def wrap(v):
                v &= m - 1
                return v - m if v >> (dt.bits - 1) else v

            def sat(v):
                return builtins.max(dt.lo, builtins.min(dt.hi, v))
            self.assertEqual(ta.wrapping_add(a, b).tolist(), [wrap(x + y) for x, y in zip(xs, ys)])
            self.assertEqual(ta.wrapping_sub(a, b).tolist(), [wrap(x - y) for x, y in zip(xs, ys)])
            self.assertEqual(ta.wrapping_mul(a, b).tolist(), [wrap(x * y) for x, y in zip(xs, ys)])
            self.assertEqual(ta.saturating_add(a, b).tolist(), [sat(x + y) for x, y in zip(xs, ys)])
            self.assertEqual(ta.saturating_sub(a, b).tolist(), [sat(x - y) for x, y in zip(xs, ys)])
            self.assertEqual(ta.wrapping_add(a, 1).tolist(), [wrap(x + 1) for x in xs])
        with self.assertRaises(TypeError):
            ta.wrapping_add(ta.zeros(2, ta.f32), ta.zeros(2, ta.f32))

    def test_in_place_prefix(self):
        a = ta.array([1, 100, 100, 1], ta.int8)
        with self.assertRaisesRegex(OverflowError, r'^int8 add overflow at index 2$'):
            a += ta.array([1, 1, 100, 1], ta.int8)
        self.assertEqual(a.tolist(), [2, 101, 100, 1])
        b = ta.array([6, 7, 8], ta.int32)
        with self.assertRaises(ZeroDivisionError):
            b //= ta.array([2, 0, 2], ta.int32)
        self.assertEqual(b.tolist(), [3, 7, 8])
        c = ta.array([1, 2], ta.int8)
        alias = c
        c += c
        self.assertIs(c, alias)
        self.assertEqual(alias.tolist(), [2, 4])

    def test_scalars(self):
        a = ta.array([1, 2, 3], ta.int8)
        self.assertEqual((a * 2).tolist(), [2, 4, 6])
        self.assertEqual((10 - a).tolist(), [9, 8, 7])
        self.assertEqual((7 // a).tolist(), [7, 3, 2])
        self.assertEqual((-7 % a).tolist(), [0, 1, 2])
        self.assertEqual((a + True).tolist(), [2, 3, 4])
        with self.assertRaisesRegex(OverflowError, '^int8 value out of range: 300$'):
            a + 300
        with self.assertRaisesRegex(TypeError, 'no implicit int-to-float'):
            a + 1.0
        with self.assertRaisesRegex(TypeError, r'^ail_array: / on int8 arrays'):
            a / a


class Mixing(unittest.TestCase):
    def test_mixed_dtypes_raise_type_error(self):
        dts = FLOATS + INTS
        for x in dts:
            for y in dts:
                if x is y:
                    continue
                a, b = ta.zeros(3, x), ta.zeros(3, y)
                for op in ('+', '-', '*'):
                    with self.assertRaisesRegex(TypeError, r'^ail_array: %s %s %s: dtypes differ' % (x, '\\' + op, y)):
                        {'+': lambda: a + b, '-': lambda: a - b, '*': lambda: a * b}[op]()
                with self.assertRaises(TypeError):
                    ta.dot(a, b)
                with self.assertRaises(TypeError):
                    a[0:1] = b[0:1]
        with self.assertRaisesRegex(TypeError, 'dtypes differ'):
            t = ta.zeros(2, ta.f32)
            t += ta.zeros(2, ta.f64)

    def test_shapes_and_other_operands(self):
        with self.assertRaisesRegex(ValueError, r'^ail_array: shapes differ: \(3,\) and \(4,\)$'):
            ta.zeros(3, ta.f32) + ta.zeros(4, ta.f32)
        with self.assertRaises(TypeError):
            ta.zeros(3, ta.f32) + 'x'
        with self.assertRaises(TypeError):
            ta.zeros(3, ta.f32) + [1.0, 2.0, 3.0]
        with self.assertRaisesRegex(TypeError, '// is not defined for f32'):
            ta.zeros(3, ta.f32) // 2.0
        with self.assertRaises(TypeError):
            ta.zeros(3, ta.f32) < ta.zeros(3, ta.f32)
        with self.assertRaises(TypeError):
            ta.zeros(3, ta.f32) @ ta.zeros(3, ta.f32)


class Casts(unittest.TestCase):
    def test_float_to_float_against_oracle(self):
        rng = random.Random(3)
        for src in FLOATS:
            vals = edge_values(src) + random_values(src, 3000, rng)
            a = ta.array(vals, src)
            for dst in FLOATS:
                got = array_bits(a.astype(dst))
                self.assertEqual(got, [round_bits_any(dst, v) for v in a.tolist()], '%s -> %s' % (src, dst))

    def test_every_f16_round_trip(self):
        raw = b''.join(k.to_bytes(2, 'little') for k in range(65536))
        a = ta.frombytes(raw, ta.f16)
        for mid in (ta.f32, ta.f64):
            back = array_bits(a.astype(mid).astype(ta.f16))
            for k, g in enumerate(back):
                is_nan = (k & 0x7c00) == 0x7c00 and k & 0x3ff
                self.assertEqual(g, CANON[ta.f16] if is_nan else k)

    def test_int_to_float(self):
        a = ta.array([0, 1, -1, 2 ** 24 + 1, 2 ** 31 - 1, -2 ** 31, 65519, 65520, 2047, 2049], ta.int32)
        for dst in FLOATS:
            self.assertEqual(array_bits(a.astype(dst)), [round_bits_any(dst, float(v)) for v in a.tolist()])
        b = ta.arange(256, ta.int32) - 128
        self.assertEqual(b.astype(ta.int8).astype(ta.f16).tolist(), [float(v) for v in range(-128, 128)])

    def test_float_to_int(self):
        a = ta.array([2.5, -2.5, 3.5, -0.7, 1e9, 127.9, -128.9], ta.f64)
        self.assertEqual(a.astype(ta.int32).tolist(), [2, -2, 3, 0, 10 ** 9, 127, -128])
        self.assertEqual(a.astype(ta.int32, rounding='nearest').tolist(), [2, -2, 4, -1, 10 ** 9, 128, -129])
        self.assertEqual(a.astype(ta.int8, overflow='saturate').tolist(), [2, -2, 3, 0, 127, 127, -128])
        with self.assertRaisesRegex(OverflowError, '^int8 cast overflow at index 4$'):
            a.astype(ta.int8)
        with self.assertRaisesRegex(OverflowError, '^int8 cast overflow at index 5$'):
            ta.array([0, 0, 0, 0, 0, 127.9], ta.f64).astype(ta.int8, rounding='nearest')
        with self.assertRaisesRegex(ValueError, '^cannot convert float NaN to integer$'):
            ta.array([math.nan], ta.f32).astype(ta.int32)
        with self.assertRaisesRegex(OverflowError, '^cannot convert float infinity to integer$'):
            ta.array([-math.inf], ta.f16).astype(ta.int8)
        sat = ta.array([math.nan, math.inf, -math.inf], ta.f32).astype(ta.int8, overflow='saturate')
        self.assertEqual(sat.tolist(), [0, 127, -128])
        with self.assertRaises(ValueError):
            a.astype(ta.int8, overflow='wrap')

    def test_int_to_int(self):
        a = ta.array([-2 ** 31, -129, -128, 127, 128, 255, 2 ** 31 - 1], ta.int32)
        self.assertEqual(a.astype(ta.int8, overflow='wrap').tolist(), [0, 127, -128, 127, -128, -1, -1])
        self.assertEqual(a.astype(ta.int8, overflow='saturate').tolist(), [-128, -128, -128, 127, 127, 127, 127])
        with self.assertRaisesRegex(OverflowError, '^int8 cast overflow at index 0$'):
            a.astype(ta.int8)
        self.assertEqual(ta.array([-128, 127], ta.int8).astype(ta.int32).tolist(), [-128, 127])
        with self.assertRaises(ValueError):
            a.astype(ta.int8, rounding='up')


class Reductions(unittest.TestCase):
    SIZES = (0, 1, 2, 15, 16, 17, 31, 33, 1023, 1024, 1025, 2048, 2049, 3071, 5000)

    def data(self, dt, n, rng):
        out = []
        for _ in range(n):
            v = math.ldexp(rng.random(), rng.randrange(-20, 12)) * rng.choice((1, -1))
            if rng.random() < 0.02:
                v = rng.choice((0.0, -0.0, 1e6, -1e6))
            out.append(v)
        return ta.array(out, dt)

    def test_sum_matches_second_implementation(self):
        rng = random.Random(9)
        for dt in FLOATS:
            for n in self.SIZES:
                a = self.data(dt, n, rng)
                A = ta.f32 if dt is ta.f16 else dt
                want = fixed_order_sum(a.tolist(), A)
                got = ta.sum(a)
                self.assertEqual(struct.pack('<d', got), struct.pack('<d', want), '%s n=%d' % (dt, n))

    def test_sum_does_not_depend_on_the_split(self):
        rng = random.Random(10)
        for dt in (ta.f32, ta.f16):
            for n in (17, 1025, 5000, 9000):
                a = self.data(dt, n, rng)
                A = ta.f32
                want = struct.pack('<d', ta.sum(a))
                xs = a.tolist()
                for width in (4, 8, 16):
                    for threads in range(1, 9):
                        got = simulated_sum(xs, A, width, threads)
                        self.assertEqual(struct.pack('<d', got), want, '%s n=%d width=%d threads=%d'
                                         % (dt, n, width, threads))

    def test_the_order_matters(self):
        # the tests above are not vacuous: a left-to-right f32 sum gives other bits for this input
        rng = random.Random(12)
        a = self.data(ta.f32, 3000, rng)
        acc = 0.0
        for v in a.tolist():
            acc = value_of(ta.f32, round_bits_any(ta.f32, acc + v))
        self.assertNotEqual(acc, ta.sum(a))

    def test_sum_details(self):
        self.assertEqual(struct.pack('<d', ta.sum(ta.zeros(0, ta.f32))), struct.pack('<d', 0.0))
        self.assertEqual(struct.pack('<d', ta.sum(ta.array([-0.0], ta.f32))), struct.pack('<d', -0.0))
        self.assertEqual(struct.pack('<d', ta.sum(ta.array([-0.0, 0.0], ta.f64))), struct.pack('<d', 0.0))
        nan = ta.sum(ta.array([1.0, math.inf, -math.inf], ta.f32))
        self.assertEqual(struct.pack('<d', nan), struct.pack('<d', ta._NAN))
        self.assertEqual(ta.sum(ta.full(5, 1.0, ta.f16)), 5.0)
        self.assertEqual(ta.sum(ta.full(4096, 1.0, ta.f16)), 4096.0)          # f32 accumulator by default
        self.assertEqual(ta.sum(ta.full(4096, 1.0, ta.f16), acc=ta.f64), 4096.0)
        with self.assertRaisesRegex(ValueError, 'would narrow'):
            ta.sum(ta.zeros(2, ta.f32), acc=ta.f16)
        with self.assertRaises(ValueError):
            ta.sum(ta.zeros(2, ta.int32), acc=ta.f64)
        self.assertEqual(ta.sum(ta.zeros(3, ta.f32), order='any'), 0.0)
        with self.assertRaises(ValueError):
            ta.sum(ta.zeros(3, ta.f32), order='fast')
        a = ta.array([0.1] * 10, ta.f64)
        self.assertEqual(builtins.sum(a), builtins.sum([0.1] * 10))            # the builtin keeps CPython's meaning
        self.assertEqual(builtins.sum(a), 1.0)

    def test_int_sums_are_exact(self):
        for dt in INTS:
            a = ta.full(3000, dt.hi, dt)
            self.assertEqual(ta.sum(a), 3000 * dt.hi)
            self.assertEqual(ta.dot(a, a), 3000 * dt.hi * dt.hi)
            b = ta.full(3000, dt.lo, dt)
            self.assertEqual(ta.sum(b), 3000 * dt.lo)
            self.assertEqual(ta.dot(a, b), 3000 * dt.hi * dt.lo)

    def test_dot(self):
        rng = random.Random(13)
        for dt in FLOATS:
            for n in (0, 5, 1025, 3000):
                a, b = self.data(dt, n, rng), self.data(dt, n, rng)
                A = ta.f32 if dt is ta.f16 else dt
                prods = [value_of(A, round_bits_any(A, x * y)) for x, y in zip(a.tolist(), b.tolist())]
                want = fixed_order_sum(prods, A)
                self.assertEqual(struct.pack('<d', ta.dot(a, b)), struct.pack('<d', want))
                if dt is not ta.f16:
                    self.assertEqual(struct.pack('<d', ta.dot(a, b)), struct.pack('<d', ta.sum(a * b)))
        with self.assertRaisesRegex(ValueError, 'shapes differ'):
            ta.dot(ta.zeros(2, ta.f32), ta.zeros(3, ta.f32))

    def test_min_max_arg(self):
        a = ta.array([3.0, 0.0, -0.0, -1.0, -1.0, 5.0, 5.0], ta.f32)
        self.assertEqual((ta.min(a), ta.argmin(a), ta.max(a), ta.argmax(a)), (-1.0, 3, 5.0, 5))
        z = ta.array([0.0, -0.0, 0.0], ta.f64)
        self.assertEqual(math.copysign(1.0, ta.min(z)), -1.0)
        self.assertEqual(ta.argmin(z), 1)
        self.assertEqual(math.copysign(1.0, ta.max(ta.array([-0.0, 0.0], ta.f64))), 1.0)
        n = ta.array([1.0, math.nan, 0.0, math.nan], ta.f16)
        self.assertTrue(ta.min(n) != ta.min(n))
        self.assertEqual((ta.argmin(n), ta.argmax(n)), (1, 1))
        self.assertEqual(struct.pack('<d', ta.max(n)), struct.pack('<d', ta._NAN))
        i = ta.array([4, -7, 9, -7, 9], ta.int8)
        self.assertEqual((ta.min(i), ta.argmin(i), ta.max(i), ta.argmax(i)), (-7, 1, 9, 2))
        with self.assertRaisesRegex(ValueError, r'^min\(\) iterable argument is empty$'):
            ta.min(ta.zeros(0, ta.f32))
        with self.assertRaisesRegex(ValueError, r'^max\(\) iterable argument is empty$'):
            ta.max(ta.zeros(0, ta.int8))
        with self.assertRaisesRegex(ValueError, 'no inexact form'):
            ta.min(a, order='any')

    def test_minimum_maximum_clip(self):
        a = ta.array([1.0, -0.0, 0.0, math.nan, 5.0], ta.f32)
        b = ta.array([2.0, 0.0, -0.0, 1.0, math.nan], ta.f32)
        self.assertEqual(array_bits(ta.minimum(a, b)), [0x3f800000, 0x80000000, 0x80000000, CANON[ta.f32],
                                                         CANON[ta.f32]])
        self.assertEqual(array_bits(ta.maximum(a, b)), [0x40000000, 0, 0, CANON[ta.f32], CANON[ta.f32]])
        self.assertEqual(ta.clip(ta.array([-5, 0, 5], ta.int8), -1, 1).tolist(), [-1, 0, 1])
        self.assertEqual(ta.clip(ta.array([-5.0, 0.5, 5.0], ta.f16), 0.0, 1.0).tolist(), [0.0, 0.5, 1.0])


class Basics(unittest.TestCase):
    def test_construction(self):
        self.assertEqual(ta.zeros(3, ta.int8).tolist(), [0, 0, 0])
        self.assertEqual(ta.zeros((2,), ta.f16).tobytes(), b'\0' * 4)
        self.assertEqual(ta.full(2, 1.5, ta.f32).tolist(), [1.5, 1.5])
        self.assertEqual(ta.arange(4, ta.int32).tolist(), [0, 1, 2, 3])
        with self.assertRaisesRegex(OverflowError, '^int8 value out of range: 128$'):
            ta.arange(200, ta.int8)
        with self.assertRaises(TypeError):
            ta.arange(3, ta.f32)
        with self.assertRaisesRegex(TypeError, "^'float' object cannot be interpreted as an integer$"):
            ta.array([1.5], ta.int32)
        with self.assertRaisesRegex(TypeError, '^must be real number, not str$'):
            ta.array(['a'], ta.f64)
        with self.assertRaisesRegex(ValueError, 'not a multiple of 4'):
            ta.frombytes(b'\0' * 7, ta.f32)
        with self.assertRaisesRegex(ValueError, 'stage T6'):
            ta.zeros((2, 3), ta.f32)
        with self.assertRaisesRegex(ValueError, '1-D and 2-D'):
            ta.zeros((2, 3, 4), ta.f32)
        with self.assertRaises(TypeError):
            ta.zeros(3, 'f32')
        xs = [1.0, 2.0]
        a = ta.array(xs, ta.f64)
        xs[0] = 9.0
        self.assertEqual(a[0], 1.0)

    def test_indexing_and_slices(self):
        a = ta.array([1, 2, 3, 4, 5], ta.int32)
        self.assertEqual((a[0], a[-1], a[True]), (1, 5, 2))
        with self.assertRaisesRegex(IndexError, '^array index out of range$'):
            a[5]
        with self.assertRaisesRegex(TypeError, '^array indices must be integers$'):
            a['x']
        s = a[1:4]
        s[0] = 99
        self.assertEqual(a.tolist(), [1, 2, 3, 4, 5])                          # slices copy
        self.assertEqual(a[::-2].tolist(), [5, 3, 1])
        a[1:3] = ta.array([7, 8], ta.int32)
        a[::4] = ta.array([0, 0], ta.int32)
        self.assertEqual(a.tolist(), [0, 7, 8, 4, 0])
        with self.assertRaises(ValueError):
            a[0:2] = ta.array([1], ta.int32)
        with self.assertRaises(TypeError):
            a[0:2] = [1, 2]
        with self.assertRaisesRegex(OverflowError, 'int32 value out of range'):
            a[0] = 2 ** 31
        f = ta.zeros(1, ta.f16)
        f[0] = 1e10
        self.assertEqual(f[0], math.inf)
        self.assertEqual(list(iter(a)), a.tolist())
        self.assertIn(8, a)
        self.assertNotIn(9, a)

    def test_equality_text_hash(self):
        a = ta.array([1.0, -0.0], ta.f32)
        self.assertEqual(a, ta.array([1.0, 0.0], ta.f32))
        self.assertNotEqual(a, ta.array([1.0, 0.0], ta.f64))
        self.assertNotEqual(a, [1.0, 0.0])
        self.assertNotEqual(ta.array([math.nan], ta.f32), ta.array([math.nan], ta.f32))
        self.assertEqual(repr(ta.array([0.1, -0.0], ta.f32)), 'array([0.10000000149011612, -0.0], f32)')
        self.assertEqual(str(ta.array([1, -2], ta.int8)), 'array([1, -2], int8)')
        self.assertEqual(repr(ta.f16), 'f16')
        with self.assertRaises(TypeError):
            hash(a)
        self.assertEqual(a.shape, (2,))
        self.assertIs(a.dtype, ta.f32)
        self.assertEqual([d.itemsize for d in (ta.f64, ta.f32, ta.f16, ta.int8, ta.int32)], [8, 4, 2, 1, 4])
        self.assertEqual(repr(ta.Array[ta.f32]), 'Array[f32]')

    def test_bytes_round_trip(self):
        rng = random.Random(4)
        for dt in FLOATS + INTS:
            raw = bytes(rng.getrandbits(8) for _ in range(dt.itemsize * 64))
            self.assertEqual(ta.frombytes(raw, dt).tobytes(), raw)
        self.assertEqual(ta.array([1, -1], ta.int32).tobytes(), struct.pack('<2i', 1, -1))
        self.assertEqual(ta.array([1.5], ta.f16).tobytes(), struct.pack('<e', 1.5))


if __name__ == '__main__':
    unittest.main()
