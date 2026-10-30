# -*- coding: utf-8 -*-
# prelude_ailarray.py -- `ail_array` (docs/design/TYPED_ARRAY.md, stages T2 and T3b) for the dtypes f64, int32, int64 and bool_, as Python source
# that the AIL compiler builds to native loops (ailarray.py rewrites the program onto these names and injects what it
# uses). It is plain Python 3.12 as well: test_ail_array_t2.py runs it under CPython against ail_array.py (the reference),
# so the two are compared op by op before any C is involved.
#
# An f64 array is a _AilTAF holding a list[float]; an int32 array is a _AilTAI and an int64 array a _AilTAL, each holding a list[int];
# a bool_ array is a _AilTAO holding a list[bool]. The functions follow the
# reference line by line (same checks in the same order, same error texts); where the reference works on the bytes of a
# bytearray, the bits of a double are made with exact float arithmetic (no struct, no frexp) because the typed path has
# neither.
import math


class _AilTAF:
    def __init__(self, n: int):
        self.d = [0.0] * n


class _AilTAI:
    def __init__(self, n: int):
        self.d = [0] * n


# ---- always-raising helpers (a statically wrong use raises at run time, as the reference does) ------------------------
def _ail_ta_te_af(msg: str) -> _AilTAF:
    if len(msg) >= 0:
        raise TypeError(msg)
    return _AilTAF(0)


def _ail_ta_te_ai(msg: str) -> _AilTAI:
    if len(msg) >= 0:
        raise TypeError(msg)
    return _AilTAI(0)


def _ail_ta_te_f(msg: str) -> float:
    if len(msg) >= 0:
        raise TypeError(msg)
    return 0.0


def _ail_ta_te_i(msg: str) -> int:
    if len(msg) >= 0:
        raise TypeError(msg)
    return 0


def _ail_ta_te_b(msg: str) -> bool:
    if len(msg) >= 0:
        raise TypeError(msg)
    return False


def _ail_ta_ve_af(msg: str) -> _AilTAF:
    if len(msg) >= 0:
        raise ValueError(msg)
    return _AilTAF(0)


def _ail_ta_ve_ai(msg: str) -> _AilTAI:
    if len(msg) >= 0:
        raise ValueError(msg)
    return _AilTAI(0)


def _ail_ta_ve_f(msg: str) -> float:
    if len(msg) >= 0:
        raise ValueError(msg)
    return 0.0


def _ail_ta_ve_i(msg: str) -> int:
    if len(msg) >= 0:
        raise ValueError(msg)
    return 0


def _ail_ta_b2i(b: bool) -> int:
    if b:
        return 1
    return 0


def _ail_ta_b2f(b: bool) -> float:
    if b:
        return 1.0
    return 0.0


def _ail_ta_canon(x: float) -> float:
    if x != x:
        return math.nan
    return x


def _ail_ta_length(n: int) -> int:
    if n < 0:
        raise ValueError("ail_array: negative length " + str(n))
    return n


def _ail_ta_shapes(n: int, m: int):
    raise ValueError("ail_array: shapes differ: (" + str(n) + ",) and (" + str(m) + ",)")


def _ail_ta_oob(n: int, i: int) -> int:
    # index i (negative allowed) of an array of length n, or IndexError
    k = i
    if k < 0:
        k = k + n
    if k < 0 or k >= n:
        raise IndexError("array index out of range")
    return k


# ---- slices: [start, count, step] as range(*slice.indices(n)) gives them -------------------------------------------------
def _ail_ta_slice(n: int, lo: int, hi: int, st: int, flags: int) -> list[int]:
    step = 1
    if flags & 4:
        step = st
    if step == 0:
        raise ValueError("slice step cannot be zero")
    start = 0
    if step < 0:
        start = n - 1
    if flags & 1:
        start = lo
        if start < 0:
            start = start + n
            if start < 0:
                start = 0
                if step < 0:
                    start = -1
        elif start >= n:
            start = n
            if step < 0:
                start = n - 1
    stop = n
    if step < 0:
        stop = -1
    if flags & 2:
        stop = hi
        if stop < 0:
            stop = stop + n
            if stop < 0:
                stop = 0
                if step < 0:
                    stop = -1
        elif stop >= n:
            stop = n
            if step < 0:
                stop = n - 1
    cnt = 0
    if step < 0:
        if stop < start:
            cnt = (start - stop - 1) // (0 - step) + 1
    else:
        if start < stop:
            cnt = (stop - start - 1) // step + 1
    return [start, cnt, step]


# ---- the bits of a double (exact float arithmetic) ---------------------------------------------------------------------
def _ail_ta_bits(x: float) -> list[int]:
    """[hi, lo]: the two 32 bit halves of the binary64 pattern of x (every NaN is the canonical 7ff8000000000000)."""
    if x != x:
        return [2146959360, 0]
    sign = 0
    y = x
    if math.copysign(1.0, y) < 0.0:
        sign = 1
        y = 0.0 - y
    top = sign * 2147483648
    if y == 0.0:
        return [top, 0]
    if y == math.inf:
        return [top + 2146435072, 0]
    if y < 2.2250738585072014e-308:
        s = int((y * 4.4989137945431964e+161) * 4.4989137945431964e+161)
        return [top + s // 4294967296, s % 4294967296]
    e = 0
    m = y
    if m >= 2.0:
        if m >= 1.3407807929942597e+154:
            m = m * 7.458340731200207e-155
            e = e + 512
        if m >= 1.157920892373162e+77:
            m = m * 8.636168555094445e-78
            e = e + 256
        if m >= 3.402823669209385e+38:
            m = m * 2.938735877055719e-39
            e = e + 128
        if m >= 1.8446744073709552e+19:
            m = m * 5.421010862427522e-20
            e = e + 64
        if m >= 4294967296.0:
            m = m * 2.3283064365386963e-10
            e = e + 32
        if m >= 65536.0:
            m = m * 1.52587890625e-05
            e = e + 16
        if m >= 256.0:
            m = m * 0.00390625
            e = e + 8
        if m >= 16.0:
            m = m * 0.0625
            e = e + 4
        if m >= 4.0:
            m = m * 0.25
            e = e + 2
        if m >= 2.0:
            m = m * 0.5
            e = e + 1
    elif m < 1.0:
        if m * 1.3407807929942597e+154 < 1.0:
            m = m * 1.3407807929942597e+154
            e = e - 512
        if m * 1.157920892373162e+77 < 1.0:
            m = m * 1.157920892373162e+77
            e = e - 256
        if m * 3.402823669209385e+38 < 1.0:
            m = m * 3.402823669209385e+38
            e = e - 128
        if m * 1.8446744073709552e+19 < 1.0:
            m = m * 1.8446744073709552e+19
            e = e - 64
        if m * 4294967296.0 < 1.0:
            m = m * 4294967296.0
            e = e - 32
        if m * 65536.0 < 1.0:
            m = m * 65536.0
            e = e - 16
        if m * 256.0 < 1.0:
            m = m * 256.0
            e = e - 8
        if m * 16.0 < 1.0:
            m = m * 16.0
            e = e - 4
        if m * 4.0 < 1.0:
            m = m * 4.0
            e = e - 2
        if m * 2.0 < 1.0:
            m = m * 2.0
            e = e - 1
        m = m * 2.0
        e = e - 1
    s = int((m - 1.0) * 4503599627370496.0)
    return [top + (e + 1023) * 1048576 + s // 4294967296, s % 4294967296]


def _ail_ta_scale(m: float, ex: int) -> float:
    """m * 2**ex for an m whose result is a normal or zero double (every step is an exact exponent change)."""
    r = m
    k = ex
    if k >= 0:
        if k >= 512:
            r = r * 1.3407807929942597e+154
            k = k - 512
        if k >= 256:
            r = r * 1.157920892373162e+77
            k = k - 256
        if k >= 128:
            r = r * 3.402823669209385e+38
            k = k - 128
        if k >= 64:
            r = r * 1.8446744073709552e+19
            k = k - 64
        if k >= 32:
            r = r * 4294967296.0
            k = k - 32
        if k >= 16:
            r = r * 65536.0
            k = k - 16
        if k >= 8:
            r = r * 256.0
            k = k - 8
        if k >= 4:
            r = r * 16.0
            k = k - 4
        if k >= 2:
            r = r * 4.0
            k = k - 2
        if k >= 1:
            r = r * 2.0
    else:
        k = 0 - k
        if k >= 512:
            r = r * 7.458340731200207e-155
            k = k - 512
        if k >= 256:
            r = r * 8.636168555094445e-78
            k = k - 256
        if k >= 128:
            r = r * 2.938735877055719e-39
            k = k - 128
        if k >= 64:
            r = r * 5.421010862427522e-20
            k = k - 64
        if k >= 32:
            r = r * 2.3283064365386963e-10
            k = k - 32
        if k >= 16:
            r = r * 1.52587890625e-05
            k = k - 16
        if k >= 8:
            r = r * 0.00390625
            k = k - 8
        if k >= 4:
            r = r * 0.0625
            k = k - 4
        if k >= 2:
            r = r * 0.25
            k = k - 2
        if k >= 1:
            r = r * 0.5
    return r


def _ail_ta_unbits(hi: int, lo: int) -> float:
    neg = hi >= 2147483648
    e = (hi // 1048576) % 2048
    mant = (hi % 1048576) * 4294967296 + lo
    r = 0.0
    if e == 2047:
        if mant != 0:
            if hi == 2146959360 and lo == 0:
                return math.nan
            raise RuntimeError("ail_array: this f64 NaN carries a sign or payload that the compiled build does not keep "
                               "(stage T2); write instead: ta.frombytes of canonical NaNs (7ff8000000000000) only")
        r = math.inf
    elif e == 0:
        r = (float(mant) * 2.2227587494850775e-162) * 2.2227587494850775e-162
    else:
        r = _ail_ta_scale(1.0 + float(mant) * 2.220446049250313e-16, e - 1023)
    if neg:
        r = -r
    return r


# ---- f64: construction -------------------------------------------------------------------------------------------------
def _ail_taf_zeros(n: int) -> _AilTAF:
    return _AilTAF(_ail_ta_length(n))


def _ail_taf_from(xs: list[float]) -> _AilTAF:
    a = _AilTAF(len(xs))
    for k in range(len(xs)):
        v = xs[k]
        if v != v:
            v = math.nan
        a.d[k] = v
    return a


def _ail_taf_full(n: int, x: float) -> _AilTAF:
    m = _ail_ta_length(n)
    a = _AilTAF(m)
    v = _ail_ta_canon(x)
    for k in range(m):
        a.d[k] = v
    return a


def _ail_taf_copy(a: _AilTAF) -> _AilTAF:
    n = len(a.d)
    b = _AilTAF(n)
    for k in range(n):
        b.d[k] = a.d[k]
    return b


def _ail_taf_frombytes(data: bytes) -> _AilTAF:
    if len(data) % 8 != 0:
        raise ValueError("ail_array: byte length " + str(len(data)) + " is not a multiple of 8 (f64)")
    n = len(data) // 8
    a = _AilTAF(n)
    for k in range(n):
        j = k * 8
        lo = data[j] + data[j + 1] * 256 + data[j + 2] * 65536 + data[j + 3] * 16777216
        hi = data[j + 4] + data[j + 5] * 256 + data[j + 6] * 65536 + data[j + 7] * 16777216
        a.d[k] = _ail_ta_unbits(hi, lo)
    return a


def _ail_taf_tobytes(a: _AilTAF) -> bytes:
    n = len(a.d)
    out = bytearray(n * 8)
    for k in range(n):
        b = _ail_ta_bits(a.d[k])
        j = k * 8
        lo = b[1]
        hi = b[0]
        out[j] = lo % 256
        out[j + 1] = (lo // 256) % 256
        out[j + 2] = (lo // 65536) % 256
        out[j + 3] = lo // 16777216
        out[j + 4] = hi % 256
        out[j + 5] = (hi // 256) % 256
        out[j + 6] = (hi // 65536) % 256
        out[j + 7] = hi // 16777216
    return bytes(out)


def _ail_taf_tolist(a: _AilTAF) -> list[float]:
    return list(a.d)


def _ail_taf_repr(a: _AilTAF) -> str:
    s = "array(["
    for k in range(len(a.d)):
        if k > 0:
            s = s + ", "
        s = s + repr(a.d[k])
    return s + "], f64)"


# ---- f64: element access ------------------------------------------------------------------------------------------------
def _ail_taf_get(a: _AilTAF, i: int) -> float:
    return a.d[_ail_ta_oob(len(a.d), i)]


def _ail_taf_set(a: _AilTAF, i: int, x: float):
    k = _ail_ta_oob(len(a.d), i)
    a.d[k] = _ail_ta_canon(x)


def _ail_taf_slice(a: _AilTAF, lo: int, hi: int, st: int, flags: int) -> _AilTAF:
    r = _ail_ta_slice(len(a.d), lo, hi, st, flags)
    out = _AilTAF(r[1])
    for j in range(r[1]):
        out.d[j] = a.d[r[0] + j * r[2]]
    return out


def _ail_taf_setslice(a: _AilTAF, lo: int, hi: int, st: int, flags: int, b: _AilTAF):
    r = _ail_ta_slice(len(a.d), lo, hi, st, flags)
    if r[1] != len(b.d):
        raise ValueError("ail_array: slice assignment needs " + str(r[1]) + " elements, not " + str(len(b.d)))
    src = list(b.d)
    for j in range(r[1]):
        a.d[r[0] + j * r[2]] = src[j]


def _ail_taf_eq(a: _AilTAF, b: _AilTAF) -> bool:
    if len(a.d) != len(b.d):
        return False
    for k in range(len(a.d)):
        if a.d[k] != b.d[k]:
            return False
    return True


def _ail_ta_ne_dtype(a: _AilTAF, b: _AilTAI) -> bool:
    return False


# ---- f64: element-wise arithmetic ---------------------------------------------------------------------------------------
def _ail_ta_fdiv0(x: float, y: float) -> float:
    if x != x or x == 0.0:
        return math.nan
    return math.copysign(math.inf, math.copysign(1.0, x) * math.copysign(1.0, y))


def _ail_taf_aa(dst: _AilTAF, a: _AilTAF, b: _AilTAF, op: int):
    """dst = a op b (op 0 + 1 - 2 * 3 /); dst may be a or b."""
    nan = math.nan
    n = len(a.d)
    if len(b.d) != n:
        _ail_ta_shapes(n, len(b.d))
    if op == 0:
        for k in range(n):
            v = a.d[k] + b.d[k]
            if v != v:
                v = nan
            dst.d[k] = v
    elif op == 1:
        for k in range(n):
            v = a.d[k] - b.d[k]
            if v != v:
                v = nan
            dst.d[k] = v
    elif op == 2:
        for k in range(n):
            v = a.d[k] * b.d[k]
            if v != v:
                v = nan
            dst.d[k] = v
    else:
        for k in range(n):
            y = b.d[k]
            v = 0.0
            if y == 0.0:
                v = _ail_ta_fdiv0(a.d[k], y)
            else:
                v = a.d[k] / y
            if v != v:
                v = nan
            dst.d[k] = v


def _ail_taf_as(dst: _AilTAF, a: _AilTAF, x: float, op: int, refl: bool):
    """dst = a op x, or x op a when refl; x is the scalar already stored to f64 (NaN canonical)."""
    nan = math.nan
    n = len(a.d)
    if op == 0:
        for k in range(n):
            v = a.d[k] + x
            if v != v:
                v = nan
            dst.d[k] = v
    elif op == 1:
        if refl:
            for k in range(n):
                v = x - a.d[k]
                if v != v:
                    v = nan
                dst.d[k] = v
        else:
            for k in range(n):
                v = a.d[k] - x
                if v != v:
                    v = nan
                dst.d[k] = v
    elif op == 2:
        for k in range(n):
            v = a.d[k] * x
            if v != v:
                v = nan
            dst.d[k] = v
    else:
        for k in range(n):
            p = a.d[k]
            q = x
            if refl:
                p = x
                q = a.d[k]
            v = 0.0
            if q == 0.0:
                v = _ail_ta_fdiv0(p, q)
            else:
                v = p / q
            if v != v:
                v = nan
            dst.d[k] = v


def _ail_taf_bin(a: _AilTAF, b: _AilTAF, op: int) -> _AilTAF:
    out = _AilTAF(len(a.d))
    _ail_taf_aa(out, a, b, op)
    return out


def _ail_taf_bin_s(a: _AilTAF, x: float, op: int, refl: bool) -> _AilTAF:
    out = _AilTAF(len(a.d))
    _ail_taf_as(out, a, _ail_ta_canon(x), op, refl)
    return out


def _ail_taf_ibin(a: _AilTAF, b: _AilTAF, op: int) -> _AilTAF:
    _ail_taf_aa(a, a, b, op)
    return a


def _ail_taf_ibin_s(a: _AilTAF, x: float, op: int) -> _AilTAF:
    _ail_taf_as(a, a, _ail_ta_canon(x), op, False)
    return a


def _ail_taf_neg(a: _AilTAF) -> _AilTAF:
    nan = math.nan
    out = _AilTAF(len(a.d))
    for k in range(len(a.d)):
        v = -a.d[k]
        if v != v:
            v = nan
        out.d[k] = v
    return out


def _ail_taf_abs(a: _AilTAF) -> _AilTAF:
    out = _AilTAF(len(a.d))
    nan = math.nan
    for k in range(len(a.d)):
        v = math.fabs(a.d[k])
        if v != v:
            v = nan
        out.d[k] = v
    return out


# ---- f64: math functions ------------------------------------------------------------------------------------------------
def _ail_taf_fn(a: _AilTAF, which: int) -> _AilTAF:
    """which: 0 sqrt, 1 exp, 2 log, 3 tanh."""
    out = _AilTAF(len(a.d))
    for k in range(len(a.d)):
        x = a.d[k]
        v = 0.0
        if x != x:
            v = math.nan
        elif which == 0:
            if x < 0.0:
                v = math.nan
            else:
                v = math.sqrt(x)
        elif which == 1:
            try:
                v = math.exp(x)
            except OverflowError:
                v = math.inf
        elif which == 2:
            if x < 0.0:
                v = math.nan
            elif x == 0.0:
                v = -math.inf
            else:
                v = math.log(x)
        else:
            v = math.tanh(x)
        if v != v:
            v = math.nan
        out.d[k] = v
    return out


# ---- f64: minimum / maximum / clip --------------------------------------------------------------------------------------
def _ail_ta_fless(x: float, y: float) -> bool:
    if x == y and x == 0.0:
        return math.copysign(1.0, x) < math.copysign(1.0, y)
    return x < y


def _ail_taf_pick_aa(a: _AilTAF, b: _AilTAF, smaller: bool) -> _AilTAF:
    n = len(a.d)
    if len(b.d) != n:
        _ail_ta_shapes(n, len(b.d))
    out = _AilTAF(n)
    nan = math.nan
    for k in range(n):
        x = a.d[k]
        y = b.d[k]
        if x != x or y != y:
            out.d[k] = nan
        elif _ail_ta_fless(y, x) == smaller:
            out.d[k] = y
        else:
            out.d[k] = x
    return out


def _ail_taf_pick_as(a: _AilTAF, s: float, smaller: bool) -> _AilTAF:
    n = len(a.d)
    y = _ail_ta_canon(s)
    out = _AilTAF(n)
    nan = math.nan
    for k in range(n):
        x = a.d[k]
        if x != x or y != y:
            out.d[k] = nan
        elif _ail_ta_fless(y, x) == smaller:
            out.d[k] = y
        else:
            out.d[k] = x
    return out


# ---- f64: reductions (the fixed order of design 3.5) -----------------------------------------------------------------------
def _ail_ta_tree(blocks: list[float], lo: int, hi: int) -> float:
    if hi - lo == 1:
        return blocks[lo]
    p = 1
    while p * 2 < hi - lo:
        p = p * 2
    return _ail_ta_tree(blocks, lo, lo + p) + _ail_ta_tree(blocks, lo + p, hi)


def _ail_taf_fsum_s(d: list[float]) -> float:
    n = len(d)
    if n == 0:
        return 0.0
    nb = (n + 1023) // 1024
    blocks = [0.0] * nb
    for b in range(nb):
        s = b * 1024
        t = s + 1024
        if t > n:
            t = n
        l0 = -0.0
        l1 = -0.0
        l2 = -0.0
        l3 = -0.0
        l4 = -0.0
        l5 = -0.0
        l6 = -0.0
        l7 = -0.0
        l8 = -0.0
        l9 = -0.0
        l10 = -0.0
        l11 = -0.0
        l12 = -0.0
        l13 = -0.0
        l14 = -0.0
        l15 = -0.0
        full = s + ((t - s) // 16) * 16
        k = s
        while k < full:
            l0 = l0 + d[k + 0]
            l1 = l1 + d[k + 1]
            l2 = l2 + d[k + 2]
            l3 = l3 + d[k + 3]
            l4 = l4 + d[k + 4]
            l5 = l5 + d[k + 5]
            l6 = l6 + d[k + 6]
            l7 = l7 + d[k + 7]
            l8 = l8 + d[k + 8]
            l9 = l9 + d[k + 9]
            l10 = l10 + d[k + 10]
            l11 = l11 + d[k + 11]
            l12 = l12 + d[k + 12]
            l13 = l13 + d[k + 13]
            l14 = l14 + d[k + 14]
            l15 = l15 + d[k + 15]
            k = k + 16
        rem = t - full
        if rem > 0:
            l0 = l0 + d[full + 0]
        if rem > 1:
            l1 = l1 + d[full + 1]
        if rem > 2:
            l2 = l2 + d[full + 2]
        if rem > 3:
            l3 = l3 + d[full + 3]
        if rem > 4:
            l4 = l4 + d[full + 4]
        if rem > 5:
            l5 = l5 + d[full + 5]
        if rem > 6:
            l6 = l6 + d[full + 6]
        if rem > 7:
            l7 = l7 + d[full + 7]
        if rem > 8:
            l8 = l8 + d[full + 8]
        if rem > 9:
            l9 = l9 + d[full + 9]
        if rem > 10:
            l10 = l10 + d[full + 10]
        if rem > 11:
            l11 = l11 + d[full + 11]
        if rem > 12:
            l12 = l12 + d[full + 12]
        if rem > 13:
            l13 = l13 + d[full + 13]
        if rem > 14:
            l14 = l14 + d[full + 14]
        if rem > 15:
            l15 = l15 + d[full + 15]
        l0 = l0 + l8
        l1 = l1 + l9
        l2 = l2 + l10
        l3 = l3 + l11
        l4 = l4 + l12
        l5 = l5 + l13
        l6 = l6 + l14
        l7 = l7 + l15
        l0 = l0 + l4
        l1 = l1 + l5
        l2 = l2 + l6
        l3 = l3 + l7
        l0 = l0 + l2
        l1 = l1 + l3
        l0 = l0 + l1
        blocks[b] = l0
    r = _ail_ta_tree(blocks, 0, nb)
    if r != r:
        return math.nan
    return r


def _ail_taf_fsum_d(d: list[float], e: list[float]) -> float:
    n = len(d)
    if n == 0:
        return 0.0
    nb = (n + 1023) // 1024
    blocks = [0.0] * nb
    for b in range(nb):
        s = b * 1024
        t = s + 1024
        if t > n:
            t = n
        l0 = -0.0
        l1 = -0.0
        l2 = -0.0
        l3 = -0.0
        l4 = -0.0
        l5 = -0.0
        l6 = -0.0
        l7 = -0.0
        l8 = -0.0
        l9 = -0.0
        l10 = -0.0
        l11 = -0.0
        l12 = -0.0
        l13 = -0.0
        l14 = -0.0
        l15 = -0.0
        full = s + ((t - s) // 16) * 16
        k = s
        while k < full:
            l0 = l0 + d[k + 0] * e[k + 0]
            l1 = l1 + d[k + 1] * e[k + 1]
            l2 = l2 + d[k + 2] * e[k + 2]
            l3 = l3 + d[k + 3] * e[k + 3]
            l4 = l4 + d[k + 4] * e[k + 4]
            l5 = l5 + d[k + 5] * e[k + 5]
            l6 = l6 + d[k + 6] * e[k + 6]
            l7 = l7 + d[k + 7] * e[k + 7]
            l8 = l8 + d[k + 8] * e[k + 8]
            l9 = l9 + d[k + 9] * e[k + 9]
            l10 = l10 + d[k + 10] * e[k + 10]
            l11 = l11 + d[k + 11] * e[k + 11]
            l12 = l12 + d[k + 12] * e[k + 12]
            l13 = l13 + d[k + 13] * e[k + 13]
            l14 = l14 + d[k + 14] * e[k + 14]
            l15 = l15 + d[k + 15] * e[k + 15]
            k = k + 16
        rem = t - full
        if rem > 0:
            l0 = l0 + d[full + 0] * e[full + 0]
        if rem > 1:
            l1 = l1 + d[full + 1] * e[full + 1]
        if rem > 2:
            l2 = l2 + d[full + 2] * e[full + 2]
        if rem > 3:
            l3 = l3 + d[full + 3] * e[full + 3]
        if rem > 4:
            l4 = l4 + d[full + 4] * e[full + 4]
        if rem > 5:
            l5 = l5 + d[full + 5] * e[full + 5]
        if rem > 6:
            l6 = l6 + d[full + 6] * e[full + 6]
        if rem > 7:
            l7 = l7 + d[full + 7] * e[full + 7]
        if rem > 8:
            l8 = l8 + d[full + 8] * e[full + 8]
        if rem > 9:
            l9 = l9 + d[full + 9] * e[full + 9]
        if rem > 10:
            l10 = l10 + d[full + 10] * e[full + 10]
        if rem > 11:
            l11 = l11 + d[full + 11] * e[full + 11]
        if rem > 12:
            l12 = l12 + d[full + 12] * e[full + 12]
        if rem > 13:
            l13 = l13 + d[full + 13] * e[full + 13]
        if rem > 14:
            l14 = l14 + d[full + 14] * e[full + 14]
        if rem > 15:
            l15 = l15 + d[full + 15] * e[full + 15]
        l0 = l0 + l8
        l1 = l1 + l9
        l2 = l2 + l10
        l3 = l3 + l11
        l4 = l4 + l12
        l5 = l5 + l13
        l6 = l6 + l14
        l7 = l7 + l15
        l0 = l0 + l4
        l1 = l1 + l5
        l2 = l2 + l6
        l3 = l3 + l7
        l0 = l0 + l2
        l1 = l1 + l3
        l0 = l0 + l1
        blocks[b] = l0
    r = _ail_ta_tree(blocks, 0, nb)
    if r != r:
        return math.nan
    return r


def _ail_ta_bsum(d: _AilTAF) -> float:
    """The value of one block (at most 1024 elements, the whole of `d`): 16 lanes, then the 8-4-2-1 tree of design 3.5.  The
    sixteen lane sums are sixteen locals and the lane of element k is the position in the unrolled group, so there is no modulo."""
    m = len(d.d)
    l0 = -0.0
    l1 = -0.0
    l2 = -0.0
    l3 = -0.0
    l4 = -0.0
    l5 = -0.0
    l6 = -0.0
    l7 = -0.0
    l8 = -0.0
    l9 = -0.0
    l10 = -0.0
    l11 = -0.0
    l12 = -0.0
    l13 = -0.0
    l14 = -0.0
    l15 = -0.0
    full = 0 + ((m - 0) // 16) * 16
    k = 0
    while k < full:
        l0 = l0 + d.d[k + 0]
        l1 = l1 + d.d[k + 1]
        l2 = l2 + d.d[k + 2]
        l3 = l3 + d.d[k + 3]
        l4 = l4 + d.d[k + 4]
        l5 = l5 + d.d[k + 5]
        l6 = l6 + d.d[k + 6]
        l7 = l7 + d.d[k + 7]
        l8 = l8 + d.d[k + 8]
        l9 = l9 + d.d[k + 9]
        l10 = l10 + d.d[k + 10]
        l11 = l11 + d.d[k + 11]
        l12 = l12 + d.d[k + 12]
        l13 = l13 + d.d[k + 13]
        l14 = l14 + d.d[k + 14]
        l15 = l15 + d.d[k + 15]
        k = k + 16
    rem = m - full
    if rem > 0:
        l0 = l0 + d.d[full + 0]
    if rem > 1:
        l1 = l1 + d.d[full + 1]
    if rem > 2:
        l2 = l2 + d.d[full + 2]
    if rem > 3:
        l3 = l3 + d.d[full + 3]
    if rem > 4:
        l4 = l4 + d.d[full + 4]
    if rem > 5:
        l5 = l5 + d.d[full + 5]
    if rem > 6:
        l6 = l6 + d.d[full + 6]
    if rem > 7:
        l7 = l7 + d.d[full + 7]
    if rem > 8:
        l8 = l8 + d.d[full + 8]
    if rem > 9:
        l9 = l9 + d.d[full + 9]
    if rem > 10:
        l10 = l10 + d.d[full + 10]
    if rem > 11:
        l11 = l11 + d.d[full + 11]
    if rem > 12:
        l12 = l12 + d.d[full + 12]
    if rem > 13:
        l13 = l13 + d.d[full + 13]
    if rem > 14:
        l14 = l14 + d.d[full + 14]
    if rem > 15:
        l15 = l15 + d.d[full + 15]
    l0 = l0 + l8
    l1 = l1 + l9
    l2 = l2 + l10
    l3 = l3 + l11
    l4 = l4 + l12
    l5 = l5 + l13
    l6 = l6 + l14
    l7 = l7 + l15
    l0 = l0 + l4
    l1 = l1 + l5
    l2 = l2 + l6
    l3 = l3 + l7
    l0 = l0 + l2
    l1 = l1 + l3
    l0 = l0 + l1
    return l0


def _ail_taf_sum(a: _AilTAF) -> float:
    return _ail_taf_fsum_s(a.d)


def _ail_taf_dot(a: _AilTAF, b: _AilTAF) -> float:
    if len(b.d) != len(a.d):
        _ail_ta_shapes(len(a.d), len(b.d))
    return _ail_taf_fsum_d(a.d, b.d)


def _ail_taf_extreme(a: _AilTAF, smaller: bool, name: str) -> list[int]:
    """[index of the min/max (the first NaN if any)]"""
    n = len(a.d)
    if n == 0:
        raise ValueError(name + "() iterable argument is empty")
    best = 0
    for k in range(n):
        x = a.d[k]
        if x != x:
            return [k]
        if k > 0:
            if smaller:
                if _ail_ta_fless(x, a.d[best]):
                    best = k
            else:
                if _ail_ta_fless(a.d[best], x):
                    best = k
    return [best]


def _ail_taf_min(a: _AilTAF) -> float:
    return _ail_ta_canon(a.d[_ail_taf_extreme(a, True, "min")[0]])


def _ail_taf_max(a: _AilTAF) -> float:
    return _ail_ta_canon(a.d[_ail_taf_extreme(a, False, "max")[0]])


def _ail_taf_argmin(a: _AilTAF) -> int:
    return _ail_taf_extreme(a, True, "argmin")[0]


def _ail_taf_argmax(a: _AilTAF) -> int:
    return _ail_taf_extreme(a, False, "argmax")[0]


# ---- f64 <-> int32 casts -----------------------------------------------------------------------------------------------------
def _ail_taf_to_i32(a: _AilTAF, nearest: bool, mode: int) -> _AilTAI:
    """astype(ta.int32): mode 0 raise, 1 saturate (wrap is a ValueError for float sources, raised by the caller)."""
    n = len(a.d)
    out = _AilTAI(n)
    for k in range(n):
        x = a.d[k]
        if x != x:
            if mode == 1:
                out.d[k] = 0
                continue
            raise ValueError("cannot convert float NaN to integer")
        if x == math.inf or x == -math.inf:
            if mode == 1:
                if x > 0.0:
                    out.d[k] = 2147483647
                else:
                    out.d[k] = -2147483648
                continue
            raise OverflowError("cannot convert float infinity to integer")
        v = 0
        if x >= 4294967296.0:
            v = 4294967296
        elif x <= -4294967296.0:
            v = -4294967296
        elif nearest:
            f = int(x)
            if float(f) > x:
                f = f - 1
            r = x - float(f)
            if r > 0.5:
                v = f + 1
            elif r < 0.5:
                v = f
            elif f % 2 == 0:
                v = f
            else:
                v = f + 1
        else:
            v = int(x)
        if v < -2147483648 or v > 2147483647:
            if mode == 1:
                if v < 0:
                    v = -2147483648
                else:
                    v = 2147483647
            else:
                raise OverflowError("int32 cast overflow at index " + str(k))
        out.d[k] = v
    return out


def _ail_taf_to_f64(a: _AilTAF) -> _AilTAF:
    n = len(a.d)
    out = _AilTAF(n)
    for k in range(n):
        out.d[k] = _ail_ta_canon(a.d[k])
    return out


# ============================== int32 ===============================================================================
def _ail_tai_zeros(n: int) -> _AilTAI:
    return _AilTAI(_ail_ta_length(n))


def _ail_tai_store(x: int) -> int:
    if x < -2147483648 or x > 2147483647:
        raise OverflowError("int32 value out of range: " + str(x))
    return x


def _ail_tai_from(xs: list[int]) -> _AilTAI:
    a = _AilTAI(len(xs))
    for k in range(len(xs)):
        a.d[k] = _ail_tai_store(xs[k])
    return a


def _ail_tai_full(n: int, x: int) -> _AilTAI:
    m = _ail_ta_length(n)
    v = _ail_tai_store(x)
    a = _AilTAI(m)
    for k in range(m):
        a.d[k] = v
    return a


def _ail_tai_arange(n: int) -> _AilTAI:
    m = _ail_ta_length(n)
    a = _AilTAI(m)
    for k in range(m):
        a.d[k] = _ail_tai_store(k)
    return a


def _ail_tai_copy(a: _AilTAI) -> _AilTAI:
    n = len(a.d)
    b = _AilTAI(n)
    for k in range(n):
        b.d[k] = a.d[k]
    return b


def _ail_tai_frombytes(data: bytes) -> _AilTAI:
    if len(data) % 4 != 0:
        raise ValueError("ail_array: byte length " + str(len(data)) + " is not a multiple of 4 (int32)")
    n = len(data) // 4
    a = _AilTAI(n)
    for k in range(n):
        j = k * 4
        u = data[j] + data[j + 1] * 256 + data[j + 2] * 65536 + data[j + 3] * 16777216
        if u >= 2147483648:
            u = u - 4294967296
        a.d[k] = u
    return a


def _ail_tai_tobytes(a: _AilTAI) -> bytes:
    n = len(a.d)
    out = bytearray(n * 4)
    for k in range(n):
        u = a.d[k]
        if u < 0:
            u = u + 4294967296
        j = k * 4
        out[j] = u % 256
        out[j + 1] = (u // 256) % 256
        out[j + 2] = (u // 65536) % 256
        out[j + 3] = u // 16777216
    return bytes(out)


def _ail_tai_tolist(a: _AilTAI) -> list[int]:
    return list(a.d)


def _ail_tai_repr(a: _AilTAI) -> str:
    s = "array(["
    for k in range(len(a.d)):
        if k > 0:
            s = s + ", "
        s = s + repr(a.d[k])
    return s + "], int32)"


def _ail_tai_get(a: _AilTAI, i: int) -> int:
    return a.d[_ail_ta_oob(len(a.d), i)]


def _ail_tai_set(a: _AilTAI, i: int, x: int):
    k = _ail_ta_oob(len(a.d), i)
    a.d[k] = _ail_tai_store(x)


def _ail_tai_set_bad(a: _AilTAI, i: int, tname: str):
    _ail_ta_oob(len(a.d), i)
    raise TypeError("'" + tname + "' object cannot be interpreted as an integer")


def _ail_tai_full_bad(n: int, tname: str) -> _AilTAI:
    _ail_ta_length(n)
    raise TypeError("'" + tname + "' object cannot be interpreted as an integer")
    return _AilTAI(0)


def _ail_tai_slice(a: _AilTAI, lo: int, hi: int, st: int, flags: int) -> _AilTAI:
    r = _ail_ta_slice(len(a.d), lo, hi, st, flags)
    out = _AilTAI(r[1])
    for j in range(r[1]):
        out.d[j] = a.d[r[0] + j * r[2]]
    return out


def _ail_tai_setslice(a: _AilTAI, lo: int, hi: int, st: int, flags: int, b: _AilTAI):
    r = _ail_ta_slice(len(a.d), lo, hi, st, flags)
    if r[1] != len(b.d):
        raise ValueError("ail_array: slice assignment needs " + str(r[1]) + " elements, not " + str(len(b.d)))
    src = list(b.d)
    for j in range(r[1]):
        a.d[r[0] + j * r[2]] = src[j]


def _ail_tai_eq(a: _AilTAI, b: _AilTAI) -> bool:
    if len(a.d) != len(b.d):
        return False
    for k in range(len(a.d)):
        if a.d[k] != b.d[k]:
            return False
    return True


def _ail_ta_ne_dtype2(a: _AilTAI, b: _AilTAF) -> bool:
    return False


def _ail_tai_over(op: int, k: int):
    name = "mod"
    if op == 0:
        name = "add"
    elif op == 1:
        name = "sub"
    elif op == 2:
        name = "mul"
    elif op == 3:
        name = "floordiv"
    raise OverflowError("int32 " + name + " overflow at index " + str(k))


def _ail_tai_aa(dst: _AilTAI, a: _AilTAI, b: _AilTAI, op: int):
    """dst = a op b (op 0 + 1 - 2 * 3 // 4 %); the elements before a failing index are written."""
    n = len(a.d)
    if len(b.d) != n:
        _ail_ta_shapes(n, len(b.d))
    for k in range(n):
        x = a.d[k]
        y = b.d[k]
        v = 0
        if op == 0:
            v = x + y
        elif op == 1:
            v = x - y
        elif op == 2:
            v = x * y
        else:
            if y == 0:
                raise ZeroDivisionError("integer division or modulo by zero")
            if op == 3:
                v = x // y
            else:
                v = x % y
        if v < -2147483648 or v > 2147483647:
            _ail_tai_over(op, k)
        dst.d[k] = v


def _ail_tai_as(dst: _AilTAI, a: _AilTAI, s: int, op: int, refl: bool):
    """dst = a op s, or s op a when refl; s is already range checked."""
    n = len(a.d)
    for k in range(n):
        x = a.d[k]
        y = s
        if refl:
            x = s
            y = a.d[k]
        v = 0
        if op == 0:
            v = x + y
        elif op == 1:
            v = x - y
        elif op == 2:
            v = x * y
        else:
            if y == 0:
                raise ZeroDivisionError("integer division or modulo by zero")
            if op == 3:
                v = x // y
            else:
                v = x % y
        if v < -2147483648 or v > 2147483647:
            _ail_tai_over(op, k)
        dst.d[k] = v


def _ail_tai_bin(a: _AilTAI, b: _AilTAI, op: int) -> _AilTAI:
    out = _AilTAI(len(a.d))
    _ail_tai_aa(out, a, b, op)
    return out


def _ail_tai_bin_s(a: _AilTAI, x: int, op: int, refl: bool) -> _AilTAI:
    s = _ail_tai_store(x)
    out = _AilTAI(len(a.d))
    _ail_tai_as(out, a, s, op, refl)
    return out


def _ail_tai_ibin(a: _AilTAI, b: _AilTAI, op: int) -> _AilTAI:
    _ail_tai_aa(a, a, b, op)
    return a


def _ail_tai_ibin_s(a: _AilTAI, x: int, op: int) -> _AilTAI:
    s = _ail_tai_store(x)
    _ail_tai_as(a, a, s, op, False)
    return a


def _ail_tai_unary(a: _AilTAI, absolute: bool) -> _AilTAI:
    out = _AilTAI(len(a.d))
    for k in range(len(a.d)):
        v = 0 - a.d[k]
        name = "neg"
        if absolute:
            v = a.d[k]
            if v < 0:
                v = 0 - v
            name = "abs"
        if v < -2147483648 or v > 2147483647:
            raise OverflowError("int32 " + name + " overflow at index " + str(k))
        out.d[k] = v
    return out


def _ail_tai_wrap(v: int) -> int:
    return (v + 2147483648) % 4294967296 - 2147483648


def _ail_tai_sat(v: int) -> int:
    if v < -2147483648:
        return -2147483648
    if v > 2147483647:
        return 2147483647
    return v


def _ail_tai_explicit(a: _AilTAI, b: _AilTAI, op: int, wrap: bool) -> _AilTAI:
    n = len(a.d)
    if len(b.d) != n:
        _ail_ta_shapes(n, len(b.d))
    out = _AilTAI(n)
    for k in range(n):
        v = 0
        if op == 0:
            v = a.d[k] + b.d[k]
        elif op == 1:
            v = a.d[k] - b.d[k]
        else:
            v = a.d[k] * b.d[k]
        if wrap:
            out.d[k] = _ail_tai_wrap(v)
        else:
            out.d[k] = _ail_tai_sat(v)
    return out


def _ail_tai_explicit_s(a: _AilTAI, x: int, op: int, wrap: bool) -> _AilTAI:
    s = _ail_tai_store(x)
    n = len(a.d)
    out = _AilTAI(n)
    for k in range(n):
        v = 0
        if op == 0:
            v = a.d[k] + s
        elif op == 1:
            v = a.d[k] - s
        else:
            v = a.d[k] * s
        if wrap:
            out.d[k] = _ail_tai_wrap(v)
        else:
            out.d[k] = _ail_tai_sat(v)
    return out


def _ail_tai_pick_aa(a: _AilTAI, b: _AilTAI, smaller: bool) -> _AilTAI:
    n = len(a.d)
    if len(b.d) != n:
        _ail_ta_shapes(n, len(b.d))
    out = _AilTAI(n)
    for k in range(n):
        x = a.d[k]
        y = b.d[k]
        if smaller:
            if y < x:
                out.d[k] = y
            else:
                out.d[k] = x
        else:
            if y > x:
                out.d[k] = y
            else:
                out.d[k] = x
    return out


def _ail_tai_pick_as(a: _AilTAI, s: int, smaller: bool) -> _AilTAI:
    y = _ail_tai_store(s)
    n = len(a.d)
    out = _AilTAI(n)
    for k in range(n):
        x = a.d[k]
        if smaller:
            if y < x:
                out.d[k] = y
            else:
                out.d[k] = x
        else:
            if y > x:
                out.d[k] = y
            else:
                out.d[k] = x
    return out


def _ail_tai_sum(a: _AilTAI) -> int:
    total = 0
    for k in range(len(a.d)):
        total = total + a.d[k]
    return total


def _ail_tai_dot(a: _AilTAI, b: _AilTAI) -> int:
    if len(b.d) != len(a.d):
        _ail_ta_shapes(len(a.d), len(b.d))
    total = 0
    for k in range(len(a.d)):
        total = total + a.d[k] * b.d[k]
    return total


def _ail_tai_extreme(a: _AilTAI, smaller: bool, name: str) -> int:
    n = len(a.d)
    if n == 0:
        raise ValueError(name + "() iterable argument is empty")
    best = 0
    for k in range(1, n):
        if smaller:
            if a.d[k] < a.d[best]:
                best = k
        else:
            if a.d[best] < a.d[k]:
                best = k
    return best


def _ail_tai_min(a: _AilTAI) -> int:
    return a.d[_ail_tai_extreme(a, True, "min")]


def _ail_tai_max(a: _AilTAI) -> int:
    return a.d[_ail_tai_extreme(a, False, "max")]


def _ail_tai_argmin(a: _AilTAI) -> int:
    return _ail_tai_extreme(a, True, "argmin")


def _ail_tai_argmax(a: _AilTAI) -> int:
    return _ail_tai_extreme(a, False, "argmax")


def _ail_tai_to_f64(a: _AilTAI) -> _AilTAF:
    n = len(a.d)
    out = _AilTAF(n)
    for k in range(n):
        out.d[k] = float(a.d[k])
    return out


# ============================== stage T3b: int64 and bool_ ==========================================================
class _AilTAL:
    def __init__(self, n: int):
        self.d = [0] * n


class _AilTAO:
    def __init__(self, n: int):
        self.d: list[bool] = [False] * n


def _ail_ta_te_al(msg: str) -> _AilTAL:
    if len(msg) >= 0:
        raise TypeError(msg)
    return _AilTAL(0)


def _ail_ta_te_ao(msg: str) -> _AilTAO:
    if len(msg) >= 0:
        raise TypeError(msg)
    return _AilTAO(0)


def _ail_ta_ve_al(msg: str) -> _AilTAL:
    if len(msg) >= 0:
        raise ValueError(msg)
    return _AilTAL(0)


def _ail_ta_ve_ao(msg: str) -> _AilTAO:
    if len(msg) >= 0:
        raise ValueError(msg)
    return _AilTAO(0)


# ---- helpers shared by the dtypes ---------------------------------------------------------------------------------------
def _ail_ta_poserr(i: int, n: int):
    raise IndexError("index " + str(i) + " is out of bounds for dimension 0 with size " + str(n))


def _ail_ta_pos(i: int, n: int) -> int:
    """Index i (negative counts from the end) of n elements, or the IndexError PyTorch's x[idx] gives."""
    k = i
    if k < 0:
        k = k + n
    if k < 0 or k >= n:
        raise IndexError("index " + str(i) + " is out of bounds for dimension 0 with size " + str(n))
    return k


def _ail_ta_positions(n: int, offset: int, shape: list[int], strides: list[int], name: str, verb: str) -> list[int]:
    """The array positions of a strided view in C order of its logical index (design TYPED_ARRAY 3.9)."""
    if len(shape) != len(strides):
        raise ValueError("ail_array." + name + "(): shape and strides differ in length (" + str(len(shape)) + " and " + str(len(strides)) + ")")
    total = 1
    for d in range(len(shape)):
        if shape[d] < 0:
            raise ValueError("ail_array." + name + "(): negative size " + str(shape[d]) + " in shape")
        total = total * shape[d]
    out = [0] * total
    if total == 0:
        return out
    idx = [0] * len(shape)
    p = offset
    for e in range(total):
        if p < 0 or p >= n:
            raise IndexError("ail_array." + name + "(): element " + str(e) + " " + verb + " index " + str(p) + ", outside the array of " + str(n) + " elements")
        out[e] = p
        d = len(shape) - 1
        while d >= 0:
            idx[d] = idx[d] + 1
            p = p + strides[d]
            if idx[d] < shape[d]:
                break
            p = p - shape[d] * strides[d]
            idx[d] = 0
            d = d - 1
    return out


def _ail_ta_segments(n: int, offs: _AilTAL, name: str) -> int:
    """Check segment offsets; the number of segments."""
    if len(offs.d) == 0:
        raise ValueError("ail_array." + name + "(): offsets needs at least one element")
    for k in range(len(offs.d)):
        o = offs.d[k]
        if o < 0 or o > n or (k > 0 and o < offs.d[k - 1]):
            raise ValueError("ail_array." + name + "(): offsets[" + str(k) + "] = " + str(o) + " is out of order or outside 0.." + str(n))
    return len(offs.d) - 1


def _ail_ta_mul32(a: int, b: int) -> int:
    """(a * b) mod 2^32 for 0 <= a, b < 2^32 without leaving int64."""
    return (a * (b & 65535) + (((a * (b >> 16)) & 65535) << 16)) & 4294967295


def _ail_tal_wmul(x: int, y: int) -> int:
    """x * y modulo 2^64 as a signed int64, with no intermediate beyond int64."""
    if x >= -2147483648 and x <= 2147483647 and y >= -2147483648 and y <= 2147483647:
        return x * y
    a0 = x & 4294967295
    a1 = (x >> 32) & 4294967295
    b0 = y & 4294967295
    b1 = (y >> 32) & 4294967295
    p1 = a0 >> 16
    p0 = a0 & 65535
    t = p1 * b0
    u = p0 * b0
    s = (t & 65535) * 65536 + u
    lo32 = s & 4294967295
    hi32 = ((t >> 16) + (s >> 32) + _ail_ta_mul32(a1, b0) + _ail_ta_mul32(a0, b1)) & 4294967295
    if hi32 >= 2147483648:
        hi32 = hi32 - 4294967296
    return hi32 * 4294967296 + lo32


def _ail_tal_wadd(x: int, y: int) -> int:
    if y > 0 and x > 9223372036854775807 - y:
        return (x - 9223372036854775807 - 1) + (y - 9223372036854775807 - 1)
    if y < 0 and x < -9223372036854775807 - 1 - y:
        return (x + 9223372036854775807 + 1) + (y + 9223372036854775807 + 1)
    return x + y


def _ail_tal_wsub(x: int, y: int) -> int:
    if y < 0 and x > 9223372036854775807 + y:
        return (x - 9223372036854775807 - 1) - (y + 9223372036854775807 + 1)
    if y > 0 and x < -9223372036854775807 - 1 + y:
        return (x + 9223372036854775807 + 1) - (y - 9223372036854775807 - 1)
    return x - y


def _ail_tal_over(op: int, k: int):
    name = "mod"
    if op == 0:
        name = "add"
    elif op == 1:
        name = "sub"
    elif op == 2:
        name = "mul"
    elif op == 3:
        name = "floordiv"
    raise OverflowError("int64 " + name + " overflow at index " + str(k))


def _ail_tal_one(x: int, y: int, op: int, k: int) -> int:
    """x op y for op 0 + 1 - 2 * 3 // 4 %, raising OverflowError / ZeroDivisionError as the reference does."""
    if op == 0:
        if (y > 0 and x > 9223372036854775807 - y) or (y < 0 and x < -9223372036854775807 - 1 - y):
            _ail_tal_over(op, k)
        return x + y
    if op == 1:
        if (y < 0 and x > 9223372036854775807 + y) or (y > 0 and x < -9223372036854775807 - 1 + y):
            _ail_tal_over(op, k)
        return x - y
    if op == 2:
        if x >= -2147483648 and x <= 2147483647 and y >= -2147483648 and y <= 2147483647:
            return x * y
        if x == 0 or y == 0:
            return 0
        if y == -1:
            if x == -9223372036854775807 - 1:
                _ail_tal_over(op, k)
            return 0 - x
        if x == -1:
            if y == -9223372036854775807 - 1:
                _ail_tal_over(op, k)
            return 0 - y
        r = _ail_tal_wmul(x, y)
        if r // y != x:
            _ail_tal_over(op, k)
        return r
    if y == 0:
        raise ZeroDivisionError("integer division or modulo by zero")
    if op == 3:
        if y == -1:
            if x == -9223372036854775807 - 1:
                _ail_tal_over(op, k)
            return 0 - x
        return x // y
    if y == -1:
        return 0
    return x % y


# ---- int64: construction and access ---------------------------------------------------------------------------------------
def _ail_tal_zeros(n: int) -> _AilTAL:
    return _AilTAL(_ail_ta_length(n))


def _ail_tal_store(x: int) -> int:
    if x < -9223372036854775807 - 1 or x > 9223372036854775807:
        raise OverflowError("int64 value out of range: " + str(x))
    return x


def _ail_tal_from(xs: list[int]) -> _AilTAL:
    a = _AilTAL(len(xs))
    for k in range(len(xs)):
        a.d[k] = _ail_tal_store(xs[k])
    return a


def _ail_tal_full(n: int, x: int) -> _AilTAL:
    m = _ail_ta_length(n)
    v = _ail_tal_store(x)
    a = _AilTAL(m)
    for k in range(m):
        a.d[k] = v
    return a


def _ail_tal_arange(n: int) -> _AilTAL:
    m = _ail_ta_length(n)
    a = _AilTAL(m)
    for k in range(m):
        a.d[k] = k
    return a


def _ail_tal_copy(a: _AilTAL) -> _AilTAL:
    n = len(a.d)
    b = _AilTAL(n)
    for k in range(n):
        b.d[k] = a.d[k]
    return b


def _ail_tal_frombytes(data: bytes) -> _AilTAL:
    if len(data) % 8 != 0:
        raise ValueError("ail_array: byte length " + str(len(data)) + " is not a multiple of 8 (int64)")
    n = len(data) // 8
    a = _AilTAL(n)
    for k in range(n):
        j = k * 8
        lo = data[j] + data[j + 1] * 256 + data[j + 2] * 65536 + data[j + 3] * 16777216
        hi = data[j + 4] + data[j + 5] * 256 + data[j + 6] * 65536 + data[j + 7] * 16777216
        if hi >= 2147483648:
            hi = hi - 4294967296
        a.d[k] = hi * 4294967296 + lo
    return a


def _ail_tal_tobytes(a: _AilTAL) -> bytes:
    n = len(a.d)
    out = bytearray(n * 8)
    for k in range(n):
        x = a.d[k]
        lo = x & 4294967295
        hi = (x >> 32) & 4294967295
        j = k * 8
        out[j] = lo % 256
        out[j + 1] = (lo // 256) % 256
        out[j + 2] = (lo // 65536) % 256
        out[j + 3] = lo // 16777216
        out[j + 4] = hi % 256
        out[j + 5] = (hi // 256) % 256
        out[j + 6] = (hi // 65536) % 256
        out[j + 7] = hi // 16777216
    return bytes(out)


def _ail_tal_tolist(a: _AilTAL) -> list[int]:
    return list(a.d)


def _ail_tal_repr(a: _AilTAL) -> str:
    s = "array(["
    for k in range(len(a.d)):
        if k > 0:
            s = s + ", "
        s = s + repr(a.d[k])
    return s + "], int64)"


def _ail_tal_get(a: _AilTAL, i: int) -> int:
    return a.d[_ail_ta_oob(len(a.d), i)]


def _ail_tal_set(a: _AilTAL, i: int, x: int):
    k = _ail_ta_oob(len(a.d), i)
    a.d[k] = _ail_tal_store(x)


def _ail_tal_set_bad(a: _AilTAL, i: int, tname: str):
    _ail_ta_oob(len(a.d), i)
    raise TypeError("'" + tname + "' object cannot be interpreted as an integer")


def _ail_tal_full_bad(n: int, tname: str) -> _AilTAL:
    _ail_ta_length(n)
    raise TypeError("'" + tname + "' object cannot be interpreted as an integer")
    return _AilTAL(0)


def _ail_tal_slice(a: _AilTAL, lo: int, hi: int, st: int, flags: int) -> _AilTAL:
    r = _ail_ta_slice(len(a.d), lo, hi, st, flags)
    out = _AilTAL(r[1])
    for j in range(r[1]):
        out.d[j] = a.d[r[0] + j * r[2]]
    return out


def _ail_tal_setslice(a: _AilTAL, lo: int, hi: int, st: int, flags: int, b: _AilTAL):
    r = _ail_ta_slice(len(a.d), lo, hi, st, flags)
    if r[1] != len(b.d):
        raise ValueError("ail_array: slice assignment needs " + str(r[1]) + " elements, not " + str(len(b.d)))
    src = list(b.d)
    for j in range(r[1]):
        a.d[r[0] + j * r[2]] = src[j]


def _ail_tal_eq(a: _AilTAL, b: _AilTAL) -> bool:
    if len(a.d) != len(b.d):
        return False
    for k in range(len(a.d)):
        if a.d[k] != b.d[k]:
            return False
    return True


# ---- int64: element-wise arithmetic (raises on overflow, as TA1) -------------------------------------------------------------
def _ail_tal_aa(dst: _AilTAL, a: _AilTAL, b: _AilTAL, op: int):
    """dst = a op b; the elements before a failing index are written."""
    n = len(a.d)
    if len(b.d) != n:
        _ail_ta_shapes(n, len(b.d))
    if op == 0:
        for k in range(n):
            x = a.d[k]
            y = b.d[k]
            if (y > 0 and x > 9223372036854775807 - y) or (y < 0 and x < -9223372036854775807 - 1 - y):
                _ail_tal_over(0, k)
            dst.d[k] = x + y
    elif op == 1:
        for k in range(n):
            x = a.d[k]
            y = b.d[k]
            if (y < 0 and x > 9223372036854775807 + y) or (y > 0 and x < -9223372036854775807 - 1 + y):
                _ail_tal_over(1, k)
            dst.d[k] = x - y
    else:
        for k in range(n):
            dst.d[k] = _ail_tal_one(a.d[k], b.d[k], op, k)


def _ail_tal_as(dst: _AilTAL, a: _AilTAL, s: int, op: int, refl: bool):
    n = len(a.d)
    if op == 0:
        for k in range(n):
            x = a.d[k]
            if (s > 0 and x > 9223372036854775807 - s) or (s < 0 and x < -9223372036854775807 - 1 - s):
                _ail_tal_over(0, k)
            dst.d[k] = x + s
    elif op == 1 and not refl:
        for k in range(n):
            x = a.d[k]
            if (s < 0 and x > 9223372036854775807 + s) or (s > 0 and x < -9223372036854775807 - 1 + s):
                _ail_tal_over(1, k)
            dst.d[k] = x - s
    else:
        for k in range(n):
            if refl:
                dst.d[k] = _ail_tal_one(s, a.d[k], op, k)
            else:
                dst.d[k] = _ail_tal_one(a.d[k], s, op, k)


def _ail_tal_bin(a: _AilTAL, b: _AilTAL, op: int) -> _AilTAL:
    out = _AilTAL(len(a.d))
    _ail_tal_aa(out, a, b, op)
    return out


def _ail_tal_bin_s(a: _AilTAL, x: int, op: int, refl: bool) -> _AilTAL:
    s = _ail_tal_store(x)
    out = _AilTAL(len(a.d))
    _ail_tal_as(out, a, s, op, refl)
    return out


def _ail_tal_ibin(a: _AilTAL, b: _AilTAL, op: int) -> _AilTAL:
    _ail_tal_aa(a, a, b, op)
    return a


def _ail_tal_ibin_s(a: _AilTAL, x: int, op: int) -> _AilTAL:
    s = _ail_tal_store(x)
    _ail_tal_as(a, a, s, op, False)
    return a


def _ail_tal_unary(a: _AilTAL, absolute: bool) -> _AilTAL:
    out = _AilTAL(len(a.d))
    for k in range(len(a.d)):
        v = a.d[k]
        name = "neg"
        if absolute:
            name = "abs"
        if v == -9223372036854775807 - 1:
            raise OverflowError("int64 " + name + " overflow at index " + str(k))
        if absolute:
            if v < 0:
                v = 0 - v
        else:
            v = 0 - v
        out.d[k] = v
    return out


def _ail_tal_sat1(x: int, y: int, op: int) -> int:
    if op == 0:
        if y > 0 and x > 9223372036854775807 - y:
            return 9223372036854775807
        if y < 0 and x < -9223372036854775807 - 1 - y:
            return -9223372036854775807 - 1
        return x + y
    if y < 0 and x > 9223372036854775807 + y:
        return 9223372036854775807
    if y > 0 and x < -9223372036854775807 - 1 + y:
        return -9223372036854775807 - 1
    return x - y


def _ail_tal_explicit(a: _AilTAL, b: _AilTAL, op: int, wrap: bool) -> _AilTAL:
    n = len(a.d)
    if len(b.d) != n:
        _ail_ta_shapes(n, len(b.d))
    out = _AilTAL(n)
    for k in range(n):
        x = a.d[k]
        y = b.d[k]
        if wrap:
            if op == 0:
                out.d[k] = _ail_tal_wadd(x, y)
            elif op == 1:
                out.d[k] = _ail_tal_wsub(x, y)
            else:
                out.d[k] = _ail_tal_wmul(x, y)
        else:
            out.d[k] = _ail_tal_sat1(x, y, op)
    return out


def _ail_tal_explicit_s(a: _AilTAL, x: int, op: int, wrap: bool) -> _AilTAL:
    y = _ail_tal_store(x)
    n = len(a.d)
    out = _AilTAL(n)
    for k in range(n):
        x = a.d[k]
        if wrap:
            if op == 0:
                out.d[k] = _ail_tal_wadd(x, y)
            elif op == 1:
                out.d[k] = _ail_tal_wsub(x, y)
            else:
                out.d[k] = _ail_tal_wmul(x, y)
        else:
            out.d[k] = _ail_tal_sat1(x, y, op)
    return out


def _ail_tal_wneg(a: _AilTAL, absolute: bool) -> _AilTAL:
    out = _AilTAL(len(a.d))
    for k in range(len(a.d)):
        v = a.d[k]
        if v == -9223372036854775807 - 1:
            out.d[k] = v
        elif absolute:
            if v < 0:
                out.d[k] = 0 - v
            else:
                out.d[k] = v
        else:
            out.d[k] = 0 - v
    return out


def _ail_tal_wfloordiv(a: _AilTAL, b: _AilTAL) -> _AilTAL:
    n = len(a.d)
    if len(b.d) != n:
        _ail_ta_shapes(n, len(b.d))
    out = _AilTAL(n)
    for k in range(n):
        x = a.d[k]
        y = b.d[k]
        if y == 0:
            raise ZeroDivisionError("integer division or modulo by zero")
        if y == -1:
            out.d[k] = _ail_tal_wmul(x, -1)
        else:
            out.d[k] = x // y
    return out


def _ail_tal_wfloordiv_s(a: _AilTAL, x: int) -> _AilTAL:
    y = _ail_tal_store(x)
    n = len(a.d)
    out = _AilTAL(n)
    for k in range(n):
        x = a.d[k]
        if y == 0:
            raise ZeroDivisionError("integer division or modulo by zero")
        if y == -1:
            out.d[k] = _ail_tal_wmul(x, -1)
        else:
            out.d[k] = x // y
    return out


def _ail_tal_pick_aa(a: _AilTAL, b: _AilTAL, smaller: bool) -> _AilTAL:
    n = len(a.d)
    if len(b.d) != n:
        _ail_ta_shapes(n, len(b.d))
    out = _AilTAL(n)
    for k in range(n):
        x = a.d[k]
        y = b.d[k]
        if smaller:
            if y < x:
                out.d[k] = y
            else:
                out.d[k] = x
        else:
            if y > x:
                out.d[k] = y
            else:
                out.d[k] = x
    return out


def _ail_tal_pick_as(a: _AilTAL, x: int, smaller: bool) -> _AilTAL:
    y = _ail_tal_store(x)
    n = len(a.d)
    out = _AilTAL(n)
    for k in range(n):
        x = a.d[k]
        if smaller:
            if y < x:
                out.d[k] = y
            else:
                out.d[k] = x
        else:
            if y > x:
                out.d[k] = y
            else:
                out.d[k] = x
    return out


# ---- int64: reductions ----------------------------------------------------------------------------------------------------
def _ail_ta_hlfold(hs: int, ls: int, wrap: bool, what: str) -> int:
    """The total of a sum kept as hs * 2^32 + ls (hs the sum of x >> 32, ls the sum of x & 0xffffffff): modulo 2^64 when wrap, else exact or OverflowError(what)."""
    if wrap:
        h32 = ((hs + 2147483648) & 4294967295) - 2147483648
        return _ail_tal_wadd(h32 * 4294967296, ls)
    q = hs + (ls >> 32)
    if q < -2147483648 or q > 2147483647:
        raise OverflowError(what)
    return q * 4294967296 + (ls & 4294967295)


def _ail_ta_isum(d: list[int], lo: int, hi: int, wrap: bool, what: str) -> int:
    hs = 0
    ls = 0
    for k in range(lo, hi):
        x = d[k]
        hs = hs + (x >> 32)
        ls = ls + (x & 4294967295)
    return _ail_ta_hlfold(hs, ls, wrap, what)


def _ail_tal_sum(a: _AilTAL) -> int:
    hs = 0
    ls = 0
    for k in range(len(a.d)):
        x = a.d[k]
        hs = hs + (x >> 32)
        ls = ls + (x & 4294967295)
    return _ail_ta_hlfold(hs, ls, False, "int64 sum overflow")


def _ail_tal_wsum(a: _AilTAL) -> int:
    hs = 0
    ls = 0
    for k in range(len(a.d)):
        x = a.d[k]
        hs = hs + (x >> 32)
        ls = ls + (x & 4294967295)
    return _ail_ta_hlfold(hs, ls, True, "")


def _ail_tal_wdot(a: _AilTAL, b: _AilTAL) -> int:
    if len(b.d) != len(a.d):
        _ail_ta_shapes(len(a.d), len(b.d))
    total = 0
    for k in range(len(a.d)):
        total = _ail_tal_wadd(total, _ail_tal_wmul(a.d[k], b.d[k]))
    return total


def _ail_tal_extreme(a: _AilTAL, smaller: bool, name: str) -> int:
    n = len(a.d)
    if n == 0:
        raise ValueError(name + "() iterable argument is empty")
    best = 0
    for k in range(1, n):
        if smaller:
            if a.d[k] < a.d[best]:
                best = k
        else:
            if a.d[best] < a.d[k]:
                best = k
    return best


def _ail_tal_min(a: _AilTAL) -> int:
    return a.d[_ail_tal_extreme(a, True, "min")]


def _ail_tal_max(a: _AilTAL) -> int:
    return a.d[_ail_tal_extreme(a, False, "max")]


def _ail_tal_argmin(a: _AilTAL) -> int:
    return _ail_tal_extreme(a, True, "argmin")


def _ail_tal_argmax(a: _AilTAL) -> int:
    return _ail_tal_extreme(a, False, "argmax")


# ---- int64 / int32 / bool_ / f64 casts ----------------------------------------------------------------------------------------
def _ail_tal_to_f64(a: _AilTAL) -> _AilTAF:
    n = len(a.d)
    out = _AilTAF(n)
    for k in range(n):
        out.d[k] = float(a.d[k])
    return out


def _ail_tai_to_i64(a: _AilTAI) -> _AilTAL:
    n = len(a.d)
    out = _AilTAL(n)
    for k in range(n):
        out.d[k] = a.d[k]
    return out


def _ail_tal_to_i32(a: _AilTAL, mode: int) -> _AilTAI:
    """astype(ta.int32): mode 0 raise, 1 saturate, 2 wrap."""
    n = len(a.d)
    out = _AilTAI(n)
    for k in range(n):
        x = a.d[k]
        if x < -2147483648 or x > 2147483647:
            if mode == 1:
                if x < 0:
                    x = -2147483648
                else:
                    x = 2147483647
            elif mode == 2:
                x = x & 4294967295
                if x >= 2147483648:
                    x = x - 4294967296
            else:
                raise OverflowError("int32 cast overflow at index " + str(k))
        out.d[k] = x
    return out


def _ail_taf_to_i64(a: _AilTAF, nearest: bool, mode: int) -> _AilTAL:
    """astype(ta.int64) of an f64 array: mode 0 raise, 1 saturate (wrap is a ValueError for float sources)."""
    n = len(a.d)
    out = _AilTAL(n)
    for k in range(n):
        x = a.d[k]
        if x != x:
            if mode == 1:
                out.d[k] = 0
                continue
            raise ValueError("cannot convert float NaN to integer")
        if x == math.inf or x == -math.inf:
            if mode == 1:
                if x > 0.0:
                    out.d[k] = 9223372036854775807
                else:
                    out.d[k] = -9223372036854775807 - 1
                continue
            raise OverflowError("cannot convert float infinity to integer")
        if x >= 9223372036854775808.0 or x < -9223372036854775808.0:
            if mode == 1:
                if x > 0.0:
                    out.d[k] = 9223372036854775807
                else:
                    out.d[k] = -9223372036854775807 - 1
                continue
            raise OverflowError("int64 cast overflow at index " + str(k))
        v = 0
        if nearest and x > -4503599627370496.0 and x < 4503599627370496.0:
            f = int(x)
            if float(f) > x:
                f = f - 1
            r = x - float(f)
            if r > 0.5:
                v = f + 1
            elif r < 0.5:
                v = f
            elif f % 2 == 0:
                v = f
            else:
                v = f + 1
        else:
            v = int(x)
        out.d[k] = v
    return out


def _ail_taf_to_bool(a: _AilTAF) -> _AilTAO:
    n = len(a.d)
    out = _AilTAO(n)
    for k in range(n):
        out.d[k] = a.d[k] != 0.0
    return out


def _ail_tai_to_bool(a: _AilTAI) -> _AilTAO:
    n = len(a.d)
    out = _AilTAO(n)
    for k in range(n):
        out.d[k] = a.d[k] != 0
    return out


def _ail_tal_to_bool(a: _AilTAL) -> _AilTAO:
    n = len(a.d)
    out = _AilTAO(n)
    for k in range(n):
        out.d[k] = a.d[k] != 0
    return out


def _ail_tao_to_f64(a: _AilTAO) -> _AilTAF:
    n = len(a.d)
    out = _AilTAF(n)
    for k in range(n):
        if a.d[k]:
            out.d[k] = 1.0
    return out


def _ail_tao_to_i32(a: _AilTAO) -> _AilTAI:
    n = len(a.d)
    out = _AilTAI(n)
    for k in range(n):
        if a.d[k]:
            out.d[k] = 1
    return out


def _ail_tao_to_i64(a: _AilTAO) -> _AilTAL:
    n = len(a.d)
    out = _AilTAL(n)
    for k in range(n):
        if a.d[k]:
            out.d[k] = 1
    return out


# ---- bool_ ----------------------------------------------------------------------------------------------------------------
def _ail_tao_zeros(n: int) -> _AilTAO:
    return _AilTAO(_ail_ta_length(n))


def _ail_tao_from(xs: list[bool]) -> _AilTAO:
    a = _AilTAO(len(xs))
    for k in range(len(xs)):
        a.d[k] = xs[k]
    return a


def _ail_tao_full(n: int, x: bool) -> _AilTAO:
    m = _ail_ta_length(n)
    a = _AilTAO(m)
    for k in range(m):
        a.d[k] = x
    return a


def _ail_tao_copy(a: _AilTAO) -> _AilTAO:
    n = len(a.d)
    b = _AilTAO(n)
    for k in range(n):
        b.d[k] = a.d[k]
    return b


def _ail_tao_frombytes(data: bytes) -> _AilTAO:
    n = len(data)
    a = _AilTAO(n)
    for k in range(n):
        a.d[k] = data[k] != 0
    return a


def _ail_tao_tobytes(a: _AilTAO) -> bytes:
    n = len(a.d)
    out = bytearray(n)
    for k in range(n):
        if a.d[k]:
            out[k] = 1
    return bytes(out)


def _ail_tao_tolist(a: _AilTAO) -> list[bool]:
    return list(a.d)


def _ail_tao_repr(a: _AilTAO) -> str:
    s = "array(["
    for k in range(len(a.d)):
        if k > 0:
            s = s + ", "
        if a.d[k]:
            s = s + "True"
        else:
            s = s + "False"
    return s + "], bool_)"


def _ail_tao_get(a: _AilTAO, i: int) -> bool:
    return a.d[_ail_ta_oob(len(a.d), i)] != 0


def _ail_tao_set(a: _AilTAO, i: int, x: bool):
    k = _ail_ta_oob(len(a.d), i)
    a.d[k] = x


def _ail_tao_set_bad(a: _AilTAO, i: int, tname: str):
    _ail_ta_oob(len(a.d), i)
    raise TypeError("'" + tname + "' object cannot be interpreted as an integer")


def _ail_tao_full_bad(n: int, tname: str) -> _AilTAO:
    _ail_ta_length(n)
    raise TypeError("'" + tname + "' object cannot be interpreted as an integer")
    return _AilTAO(0)


def _ail_tao_slice(a: _AilTAO, lo: int, hi: int, st: int, flags: int) -> _AilTAO:
    r = _ail_ta_slice(len(a.d), lo, hi, st, flags)
    out = _AilTAO(r[1])
    for j in range(r[1]):
        out.d[j] = a.d[r[0] + j * r[2]]
    return out


def _ail_tao_setslice(a: _AilTAO, lo: int, hi: int, st: int, flags: int, b: _AilTAO):
    r = _ail_ta_slice(len(a.d), lo, hi, st, flags)
    if r[1] != len(b.d):
        raise ValueError("ail_array: slice assignment needs " + str(r[1]) + " elements, not " + str(len(b.d)))
    src = list(b.d)
    for j in range(r[1]):
        a.d[r[0] + j * r[2]] = src[j]


def _ail_tao_eq(a: _AilTAO, b: _AilTAO) -> bool:
    if len(a.d) != len(b.d):
        return False
    for k in range(len(a.d)):
        if a.d[k] != b.d[k]:
            return False
    return True


def _ail_tao_logic(a: _AilTAO, b: _AilTAO, op: int) -> _AilTAO:
    """op 0 and, 1 or, 2 xor."""
    n = len(a.d)
    if len(b.d) != n:
        _ail_ta_shapes(n, len(b.d))
    out = _AilTAO(n)
    for k in range(n):
        x = a.d[k]
        y = b.d[k]
        if op == 0:
            out.d[k] = x == True and y == True
        elif op == 1:
            out.d[k] = x == True or y == True
        else:
            out.d[k] = x != y
    return out


def _ail_tao_logic_s(a: _AilTAO, y: bool, op: int) -> _AilTAO:
    n = len(a.d)
    out = _AilTAO(n)
    for k in range(n):
        x = a.d[k]
        if op == 0:
            out.d[k] = x == True and y == True
        elif op == 1:
            out.d[k] = x == True or y == True
        else:
            out.d[k] = x != y
    return out


def _ail_tao_not(a: _AilTAO) -> _AilTAO:
    n = len(a.d)
    out = _AilTAO(n)
    for k in range(n):
        out.d[k] = not a.d[k]
    return out


def _ail_tao_sum(a: _AilTAO) -> int:
    total = 0
    for k in range(len(a.d)):
        if a.d[k]:
            total = total + 1
    return total


def _ail_tao_extreme(a: _AilTAO, smaller: bool, name: str) -> int:
    n = len(a.d)
    if n == 0:
        raise ValueError(name + "() iterable argument is empty")
    best = 0
    for k in range(1, n):
        if smaller:
            if (not a.d[k]) and a.d[best]:
                best = k
        else:
            if a.d[k] and (not a.d[best]):
                best = k
    return best


def _ail_tao_min(a: _AilTAO) -> bool:
    return a.d[_ail_tao_extreme(a, True, "min")] != 0


def _ail_tao_max(a: _AilTAO) -> bool:
    return a.d[_ail_tao_extreme(a, False, "max")] != 0


def _ail_tao_argmin(a: _AilTAO) -> int:
    return _ail_tao_extreme(a, True, "argmin")


def _ail_tao_argmax(a: _AilTAO) -> int:
    return _ail_tao_extreme(a, False, "argmax")


def _ail_tao_pick_aa(a: _AilTAO, b: _AilTAO, smaller: bool) -> _AilTAO:
    n = len(a.d)
    if len(b.d) != n:
        _ail_ta_shapes(n, len(b.d))
    out = _AilTAO(n)
    for k in range(n):
        x = a.d[k]
        y = b.d[k]
        if smaller:
            out.d[k] = x == True and y == True
        else:
            out.d[k] = x == True or y == True
    return out


def _ail_tao_pick_as(a: _AilTAO, y: bool, smaller: bool) -> _AilTAO:
    n = len(a.d)
    out = _AilTAO(n)
    for k in range(n):
        x = a.d[k]
        if smaller:
            out.d[k] = x == True and y == True
        else:
            out.d[k] = x == True or y == True
    return out


# ---- int32 additions of stage T3b ---------------------------------------------------------------------------------------
def _ail_tai_wneg(a: _AilTAI, absolute: bool) -> _AilTAI:
    out = _AilTAI(len(a.d))
    for k in range(len(a.d)):
        v = 0 - a.d[k]
        if absolute and a.d[k] >= 0:
            v = a.d[k]
        out.d[k] = _ail_tai_wrap(v)
    return out


def _ail_tai_wfloordiv(a: _AilTAI, b: _AilTAI) -> _AilTAI:
    n = len(a.d)
    if len(b.d) != n:
        _ail_ta_shapes(n, len(b.d))
    out = _AilTAI(n)
    for k in range(n):
        if b.d[k] == 0:
            raise ZeroDivisionError("integer division or modulo by zero")
        out.d[k] = _ail_tai_wrap(a.d[k] // b.d[k])
    return out


def _ail_tai_wfloordiv_s(a: _AilTAI, y: int) -> _AilTAI:
    n = len(a.d)
    out = _AilTAI(n)
    for k in range(n):
        if y == 0:
            raise ZeroDivisionError("integer division or modulo by zero")
        out.d[k] = _ail_tai_wrap(a.d[k] // y)
    return out


def _ail_taf_cmp(a: _AilTAF, b: _AilTAF, op: int) -> _AilTAO:
    n = len(a.d)
    if len(b.d) != n:
        _ail_ta_shapes(n, len(b.d))
    out = _AilTAO(n)
    for k in range(n):
        x = a.d[k]
        y = b.d[k]
        if op == 0:
            out.d[k] = x == y
        elif op == 1:
            out.d[k] = x != y
        elif op == 2:
            out.d[k] = x < y
        elif op == 3:
            out.d[k] = x <= y
        elif op == 4:
            out.d[k] = x > y
        else:
            out.d[k] = x >= y
    return out


def _ail_taf_cmp_s(a: _AilTAF, y: float, op: int) -> _AilTAO:
    n = len(a.d)
    out = _AilTAO(n)
    for k in range(n):
        x = a.d[k]
        if op == 0:
            out.d[k] = x == y
        elif op == 1:
            out.d[k] = x != y
        elif op == 2:
            out.d[k] = x < y
        elif op == 3:
            out.d[k] = x <= y
        elif op == 4:
            out.d[k] = x > y
        else:
            out.d[k] = x >= y
    return out


def _ail_taf_where_aa(m: _AilTAO, a: _AilTAF, b: _AilTAF) -> _AilTAF:
    n = len(a.d)
    if len(b.d) != n:
        _ail_ta_shapes(n, len(b.d))
    if len(m.d) != n:
        _ail_ta_shapes(len(m.d), n)
    out = _AilTAF(n)
    for k in range(n):
        if m.d[k]:
            out.d[k] = a.d[k]
        else:
            out.d[k] = b.d[k]
    return out


def _ail_taf_where_as(m: _AilTAO, a: _AilTAF, y: float) -> _AilTAF:
    n = len(a.d)
    if len(m.d) != n:
        _ail_ta_shapes(len(m.d), n)
    out = _AilTAF(n)
    for k in range(n):
        if m.d[k]:
            out.d[k] = a.d[k]
        else:
            out.d[k] = y
    return out


def _ail_taf_where_sa(m: _AilTAO, x: float, b: _AilTAF) -> _AilTAF:
    n = len(b.d)
    if len(m.d) != n:
        _ail_ta_shapes(len(m.d), n)
    out = _AilTAF(n)
    for k in range(n):
        if m.d[k]:
            out.d[k] = x
        else:
            out.d[k] = b.d[k]
    return out


def _ail_taf_any(a: _AilTAF) -> bool:
    for k in range(len(a.d)):
        if a.d[k] != 0.0:
            return True
    return False


def _ail_taf_all(a: _AilTAF) -> bool:
    for k in range(len(a.d)):
        if not (a.d[k] != 0.0):
            return False
    return True


def _ail_taf_take(a: _AilTAF, idx: _AilTAL) -> _AilTAF:
    n = len(a.d)
    out = _AilTAF(len(idx.d))
    for j in range(len(idx.d)):
        i = idx.d[j]
        k = i
        if k < 0:
            k = k + n
        if k < 0 or k >= n:
            _ail_ta_poserr(i, n)
        out.d[j] = a.d[k]
    return out


def _ail_taf_put(a: _AilTAF, idx: _AilTAL, src: _AilTAF):
    if len(src.d) != len(idx.d):
        raise ValueError("ail_array.put(): src has " + str(len(src.d)) + " elements but there are " + str(len(idx.d)) + " indices")
    s = list(src.d)
    for j in range(len(idx.d)):
        a.d[_ail_ta_pos(idx.d[j], len(a.d))] = s[j]


def _ail_taf_put_s(a: _AilTAF, idx: _AilTAL, x: float):
    for j in range(len(idx.d)):
        a.d[_ail_ta_pos(idx.d[j], len(a.d))] = x


def _ail_taf_gstride(a: _AilTAF, offset: int, shape: list[int], strides: list[int]) -> _AilTAF:
    ps = _ail_ta_positions(len(a.d), offset, shape, strides, "gather_strided", "reads")
    out = _AilTAF(len(ps))
    for j in range(len(ps)):
        out.d[j] = a.d[ps[j]]
    return out


def _ail_taf_sstride(dst: _AilTAF, offset: int, shape: list[int], strides: list[int], src: _AilTAF):
    ps = _ail_ta_positions(len(dst.d), offset, shape, strides, "scatter_strided", "writes")
    if len(src.d) != len(ps):
        raise ValueError("ail_array.scatter_strided(): src has " + str(len(src.d)) + " elements but the shape has " + str(len(ps)))
    s = list(src.d)
    for j in range(len(ps)):
        dst.d[ps[j]] = s[j]


def _ail_taf_sstride_s(dst: _AilTAF, offset: int, shape: list[int], strides: list[int], x: float):
    ps = _ail_ta_positions(len(dst.d), offset, shape, strides, "scatter_strided", "writes")
    for j in range(len(ps)):
        dst.d[ps[j]] = x


def _ail_taf_segbest(a: _AilTAF, offs: _AilTAL, smaller: bool, name: str) -> list[int]:
    ns = _ail_ta_segments(len(a.d), offs, name)
    res = [0] * ns
    for s in range(ns):
        lo = offs.d[s]
        hi = offs.d[s + 1]
        if lo == hi:
            raise ValueError("ail_array." + name + "(): segment " + str(s) + " is empty")
        best = lo
        for j in range(lo, hi):
            x = a.d[j]
            if x != x:
                best = j
                break
            if j > lo:
                if smaller:
                    if _ail_ta_fless(x, a.d[best]):
                        best = j
                else:
                    if _ail_ta_fless(a.d[best], x):
                        best = j
        res[s] = best
    return res


def _ail_taf_segmin(a: _AilTAF, offs: _AilTAL) -> _AilTAF:
    r = _ail_taf_segbest(a, offs, True, "segment_min")
    out = _AilTAF(len(r))
    for s in range(len(r)):
        out.d[s] = _ail_ta_canon(a.d[r[s]])
    return out


def _ail_taf_segmax(a: _AilTAF, offs: _AilTAL) -> _AilTAF:
    r = _ail_taf_segbest(a, offs, False, "segment_max")
    out = _AilTAF(len(r))
    for s in range(len(r)):
        out.d[s] = _ail_ta_canon(a.d[r[s]])
    return out


def _ail_taf_segargmin(a: _AilTAF, offs: _AilTAL) -> _AilTAL:
    r = _ail_taf_segbest(a, offs, True, "segment_argmin")
    out = _AilTAL(len(r))
    for s in range(len(r)):
        out.d[s] = r[s] - offs.d[s]
    return out


def _ail_taf_segargmax(a: _AilTAF, offs: _AilTAL) -> _AilTAL:
    r = _ail_taf_segbest(a, offs, False, "segment_argmax")
    out = _AilTAL(len(r))
    for s in range(len(r)):
        out.d[s] = r[s] - offs.d[s]
    return out


def _ail_taf_put_add(a: _AilTAF, idx: _AilTAL, src: _AilTAF, wrap: bool):
    if len(src.d) != len(idx.d):
        raise ValueError("ail_array.put(): src has " + str(len(src.d)) + " elements but there are " + str(len(idx.d)) + " indices")
    s = list(src.d)
    for j in range(len(idx.d)):
        k = _ail_ta_pos(idx.d[j], len(a.d))
        a.d[k] = _ail_ta_canon(a.d[k] + s[j])


def _ail_taf_put_add_s(a: _AilTAF, idx: _AilTAL, x: float, wrap: bool):
    s = [x] * len(idx.d)
    for j in range(len(idx.d)):
        k = _ail_ta_pos(idx.d[j], len(a.d))
        a.d[k] = _ail_ta_canon(a.d[k] + s[j])


def _ail_tai_cmp(a: _AilTAI, b: _AilTAI, op: int) -> _AilTAO:
    n = len(a.d)
    if len(b.d) != n:
        _ail_ta_shapes(n, len(b.d))
    out = _AilTAO(n)
    for k in range(n):
        x = a.d[k]
        y = b.d[k]
        if op == 0:
            out.d[k] = x == y
        elif op == 1:
            out.d[k] = x != y
        elif op == 2:
            out.d[k] = x < y
        elif op == 3:
            out.d[k] = x <= y
        elif op == 4:
            out.d[k] = x > y
        else:
            out.d[k] = x >= y
    return out


def _ail_tai_cmp_s(a: _AilTAI, y: int, op: int) -> _AilTAO:
    n = len(a.d)
    out = _AilTAO(n)
    for k in range(n):
        x = a.d[k]
        if op == 0:
            out.d[k] = x == y
        elif op == 1:
            out.d[k] = x != y
        elif op == 2:
            out.d[k] = x < y
        elif op == 3:
            out.d[k] = x <= y
        elif op == 4:
            out.d[k] = x > y
        else:
            out.d[k] = x >= y
    return out


def _ail_tai_where_aa(m: _AilTAO, a: _AilTAI, b: _AilTAI) -> _AilTAI:
    n = len(a.d)
    if len(b.d) != n:
        _ail_ta_shapes(n, len(b.d))
    if len(m.d) != n:
        _ail_ta_shapes(len(m.d), n)
    out = _AilTAI(n)
    for k in range(n):
        if m.d[k]:
            out.d[k] = a.d[k]
        else:
            out.d[k] = b.d[k]
    return out


def _ail_tai_where_as(m: _AilTAO, a: _AilTAI, y: int) -> _AilTAI:
    n = len(a.d)
    if len(m.d) != n:
        _ail_ta_shapes(len(m.d), n)
    out = _AilTAI(n)
    for k in range(n):
        if m.d[k]:
            out.d[k] = a.d[k]
        else:
            out.d[k] = y
    return out


def _ail_tai_where_sa(m: _AilTAO, x: int, b: _AilTAI) -> _AilTAI:
    n = len(b.d)
    if len(m.d) != n:
        _ail_ta_shapes(len(m.d), n)
    out = _AilTAI(n)
    for k in range(n):
        if m.d[k]:
            out.d[k] = x
        else:
            out.d[k] = b.d[k]
    return out


def _ail_tai_any(a: _AilTAI) -> bool:
    for k in range(len(a.d)):
        if a.d[k] != 0:
            return True
    return False


def _ail_tai_all(a: _AilTAI) -> bool:
    for k in range(len(a.d)):
        if not (a.d[k] != 0):
            return False
    return True


def _ail_tai_take(a: _AilTAI, idx: _AilTAL) -> _AilTAI:
    n = len(a.d)
    out = _AilTAI(len(idx.d))
    for j in range(len(idx.d)):
        i = idx.d[j]
        k = i
        if k < 0:
            k = k + n
        if k < 0 or k >= n:
            _ail_ta_poserr(i, n)
        out.d[j] = a.d[k]
    return out


def _ail_tai_put(a: _AilTAI, idx: _AilTAL, src: _AilTAI):
    if len(src.d) != len(idx.d):
        raise ValueError("ail_array.put(): src has " + str(len(src.d)) + " elements but there are " + str(len(idx.d)) + " indices")
    s = list(src.d)
    for j in range(len(idx.d)):
        a.d[_ail_ta_pos(idx.d[j], len(a.d))] = s[j]


def _ail_tai_put_s(a: _AilTAI, idx: _AilTAL, x: int):
    for j in range(len(idx.d)):
        a.d[_ail_ta_pos(idx.d[j], len(a.d))] = x


def _ail_tai_gstride(a: _AilTAI, offset: int, shape: list[int], strides: list[int]) -> _AilTAI:
    ps = _ail_ta_positions(len(a.d), offset, shape, strides, "gather_strided", "reads")
    out = _AilTAI(len(ps))
    for j in range(len(ps)):
        out.d[j] = a.d[ps[j]]
    return out


def _ail_tai_sstride(dst: _AilTAI, offset: int, shape: list[int], strides: list[int], src: _AilTAI):
    ps = _ail_ta_positions(len(dst.d), offset, shape, strides, "scatter_strided", "writes")
    if len(src.d) != len(ps):
        raise ValueError("ail_array.scatter_strided(): src has " + str(len(src.d)) + " elements but the shape has " + str(len(ps)))
    s = list(src.d)
    for j in range(len(ps)):
        dst.d[ps[j]] = s[j]


def _ail_tai_sstride_s(dst: _AilTAI, offset: int, shape: list[int], strides: list[int], x: int):
    ps = _ail_ta_positions(len(dst.d), offset, shape, strides, "scatter_strided", "writes")
    for j in range(len(ps)):
        dst.d[ps[j]] = x


def _ail_tai_segbest(a: _AilTAI, offs: _AilTAL, smaller: bool, name: str) -> list[int]:
    ns = _ail_ta_segments(len(a.d), offs, name)
    res = [0] * ns
    for s in range(ns):
        lo = offs.d[s]
        hi = offs.d[s + 1]
        if lo == hi:
            raise ValueError("ail_array." + name + "(): segment " + str(s) + " is empty")
        best = lo
        for j in range(lo, hi):
            x = a.d[j]
            if j > lo:
                if smaller:
                    if x < a.d[best]:
                        best = j
                else:
                    if a.d[best] < x:
                        best = j
        res[s] = best
    return res


def _ail_tai_segmin(a: _AilTAI, offs: _AilTAL) -> _AilTAI:
    r = _ail_tai_segbest(a, offs, True, "segment_min")
    out = _AilTAI(len(r))
    for s in range(len(r)):
        out.d[s] = a.d[r[s]]
    return out


def _ail_tai_segmax(a: _AilTAI, offs: _AilTAL) -> _AilTAI:
    r = _ail_tai_segbest(a, offs, False, "segment_max")
    out = _AilTAI(len(r))
    for s in range(len(r)):
        out.d[s] = a.d[r[s]]
    return out


def _ail_tai_segargmin(a: _AilTAI, offs: _AilTAL) -> _AilTAL:
    r = _ail_tai_segbest(a, offs, True, "segment_argmin")
    out = _AilTAL(len(r))
    for s in range(len(r)):
        out.d[s] = r[s] - offs.d[s]
    return out


def _ail_tai_segargmax(a: _AilTAI, offs: _AilTAL) -> _AilTAL:
    r = _ail_tai_segbest(a, offs, False, "segment_argmax")
    out = _AilTAL(len(r))
    for s in range(len(r)):
        out.d[s] = r[s] - offs.d[s]
    return out


def _ail_tai_put_add(a: _AilTAI, idx: _AilTAL, src: _AilTAI, wrap: bool):
    if len(src.d) != len(idx.d):
        raise ValueError("ail_array.put(): src has " + str(len(src.d)) + " elements but there are " + str(len(idx.d)) + " indices")
    s = list(src.d)
    for j in range(len(idx.d)):
        k = _ail_ta_pos(idx.d[j], len(a.d))
        a.d[k] = _ail_tai_addchk(a.d[k], s[j], j, wrap)


def _ail_tai_put_add_s(a: _AilTAI, idx: _AilTAL, x: int, wrap: bool):
    s = [x] * len(idx.d)
    for j in range(len(idx.d)):
        k = _ail_ta_pos(idx.d[j], len(a.d))
        a.d[k] = _ail_tai_addchk(a.d[k], s[j], j, wrap)


def _ail_tal_cmp(a: _AilTAL, b: _AilTAL, op: int) -> _AilTAO:
    n = len(a.d)
    if len(b.d) != n:
        _ail_ta_shapes(n, len(b.d))
    out = _AilTAO(n)
    for k in range(n):
        x = a.d[k]
        y = b.d[k]
        if op == 0:
            out.d[k] = x == y
        elif op == 1:
            out.d[k] = x != y
        elif op == 2:
            out.d[k] = x < y
        elif op == 3:
            out.d[k] = x <= y
        elif op == 4:
            out.d[k] = x > y
        else:
            out.d[k] = x >= y
    return out


def _ail_tal_cmp_s(a: _AilTAL, y: int, op: int) -> _AilTAO:
    n = len(a.d)
    out = _AilTAO(n)
    for k in range(n):
        x = a.d[k]
        if op == 0:
            out.d[k] = x == y
        elif op == 1:
            out.d[k] = x != y
        elif op == 2:
            out.d[k] = x < y
        elif op == 3:
            out.d[k] = x <= y
        elif op == 4:
            out.d[k] = x > y
        else:
            out.d[k] = x >= y
    return out


def _ail_tal_where_aa(m: _AilTAO, a: _AilTAL, b: _AilTAL) -> _AilTAL:
    n = len(a.d)
    if len(b.d) != n:
        _ail_ta_shapes(n, len(b.d))
    if len(m.d) != n:
        _ail_ta_shapes(len(m.d), n)
    out = _AilTAL(n)
    for k in range(n):
        if m.d[k]:
            out.d[k] = a.d[k]
        else:
            out.d[k] = b.d[k]
    return out


def _ail_tal_where_as(m: _AilTAO, a: _AilTAL, y: int) -> _AilTAL:
    n = len(a.d)
    if len(m.d) != n:
        _ail_ta_shapes(len(m.d), n)
    out = _AilTAL(n)
    for k in range(n):
        if m.d[k]:
            out.d[k] = a.d[k]
        else:
            out.d[k] = y
    return out


def _ail_tal_where_sa(m: _AilTAO, x: int, b: _AilTAL) -> _AilTAL:
    n = len(b.d)
    if len(m.d) != n:
        _ail_ta_shapes(len(m.d), n)
    out = _AilTAL(n)
    for k in range(n):
        if m.d[k]:
            out.d[k] = x
        else:
            out.d[k] = b.d[k]
    return out


def _ail_tal_any(a: _AilTAL) -> bool:
    for k in range(len(a.d)):
        if a.d[k] != 0:
            return True
    return False


def _ail_tal_all(a: _AilTAL) -> bool:
    for k in range(len(a.d)):
        if not (a.d[k] != 0):
            return False
    return True


def _ail_tal_take(a: _AilTAL, idx: _AilTAL) -> _AilTAL:
    n = len(a.d)
    out = _AilTAL(len(idx.d))
    for j in range(len(idx.d)):
        i = idx.d[j]
        k = i
        if k < 0:
            k = k + n
        if k < 0 or k >= n:
            _ail_ta_poserr(i, n)
        out.d[j] = a.d[k]
    return out


def _ail_tal_put(a: _AilTAL, idx: _AilTAL, src: _AilTAL):
    if len(src.d) != len(idx.d):
        raise ValueError("ail_array.put(): src has " + str(len(src.d)) + " elements but there are " + str(len(idx.d)) + " indices")
    s = list(src.d)
    for j in range(len(idx.d)):
        a.d[_ail_ta_pos(idx.d[j], len(a.d))] = s[j]


def _ail_tal_put_s(a: _AilTAL, idx: _AilTAL, x: int):
    for j in range(len(idx.d)):
        a.d[_ail_ta_pos(idx.d[j], len(a.d))] = x


def _ail_tal_gstride(a: _AilTAL, offset: int, shape: list[int], strides: list[int]) -> _AilTAL:
    ps = _ail_ta_positions(len(a.d), offset, shape, strides, "gather_strided", "reads")
    out = _AilTAL(len(ps))
    for j in range(len(ps)):
        out.d[j] = a.d[ps[j]]
    return out


def _ail_tal_sstride(dst: _AilTAL, offset: int, shape: list[int], strides: list[int], src: _AilTAL):
    ps = _ail_ta_positions(len(dst.d), offset, shape, strides, "scatter_strided", "writes")
    if len(src.d) != len(ps):
        raise ValueError("ail_array.scatter_strided(): src has " + str(len(src.d)) + " elements but the shape has " + str(len(ps)))
    s = list(src.d)
    for j in range(len(ps)):
        dst.d[ps[j]] = s[j]


def _ail_tal_sstride_s(dst: _AilTAL, offset: int, shape: list[int], strides: list[int], x: int):
    ps = _ail_ta_positions(len(dst.d), offset, shape, strides, "scatter_strided", "writes")
    for j in range(len(ps)):
        dst.d[ps[j]] = x


def _ail_tal_segbest(a: _AilTAL, offs: _AilTAL, smaller: bool, name: str) -> list[int]:
    ns = _ail_ta_segments(len(a.d), offs, name)
    res = [0] * ns
    for s in range(ns):
        lo = offs.d[s]
        hi = offs.d[s + 1]
        if lo == hi:
            raise ValueError("ail_array." + name + "(): segment " + str(s) + " is empty")
        best = lo
        for j in range(lo, hi):
            x = a.d[j]
            if j > lo:
                if smaller:
                    if x < a.d[best]:
                        best = j
                else:
                    if a.d[best] < x:
                        best = j
        res[s] = best
    return res


def _ail_tal_segmin(a: _AilTAL, offs: _AilTAL) -> _AilTAL:
    r = _ail_tal_segbest(a, offs, True, "segment_min")
    out = _AilTAL(len(r))
    for s in range(len(r)):
        out.d[s] = a.d[r[s]]
    return out


def _ail_tal_segmax(a: _AilTAL, offs: _AilTAL) -> _AilTAL:
    r = _ail_tal_segbest(a, offs, False, "segment_max")
    out = _AilTAL(len(r))
    for s in range(len(r)):
        out.d[s] = a.d[r[s]]
    return out


def _ail_tal_segargmin(a: _AilTAL, offs: _AilTAL) -> _AilTAL:
    r = _ail_tal_segbest(a, offs, True, "segment_argmin")
    out = _AilTAL(len(r))
    for s in range(len(r)):
        out.d[s] = r[s] - offs.d[s]
    return out


def _ail_tal_segargmax(a: _AilTAL, offs: _AilTAL) -> _AilTAL:
    r = _ail_tal_segbest(a, offs, False, "segment_argmax")
    out = _AilTAL(len(r))
    for s in range(len(r)):
        out.d[s] = r[s] - offs.d[s]
    return out


def _ail_tal_put_add(a: _AilTAL, idx: _AilTAL, src: _AilTAL, wrap: bool):
    if len(src.d) != len(idx.d):
        raise ValueError("ail_array.put(): src has " + str(len(src.d)) + " elements but there are " + str(len(idx.d)) + " indices")
    s = list(src.d)
    for j in range(len(idx.d)):
        k = _ail_ta_pos(idx.d[j], len(a.d))
        a.d[k] = _ail_tal_addchk(a.d[k], s[j], j, wrap)


def _ail_tal_put_add_s(a: _AilTAL, idx: _AilTAL, x: int, wrap: bool):
    s = [x] * len(idx.d)
    for j in range(len(idx.d)):
        k = _ail_ta_pos(idx.d[j], len(a.d))
        a.d[k] = _ail_tal_addchk(a.d[k], s[j], j, wrap)


def _ail_tao_cmp(a: _AilTAO, b: _AilTAO, op: int) -> _AilTAO:
    n = len(a.d)
    if len(b.d) != n:
        _ail_ta_shapes(n, len(b.d))
    out = _AilTAO(n)
    for k in range(n):
        x = a.d[k]
        y = b.d[k]
        if op == 0:
            out.d[k] = x == y
        elif op == 1:
            out.d[k] = x != y
        elif op == 2:
            out.d[k] = x < y
        elif op == 3:
            out.d[k] = x <= y
        elif op == 4:
            out.d[k] = x > y
        else:
            out.d[k] = x >= y
    return out


def _ail_tao_cmp_s(a: _AilTAO, y: bool, op: int) -> _AilTAO:
    n = len(a.d)
    out = _AilTAO(n)
    for k in range(n):
        x = a.d[k]
        if op == 0:
            out.d[k] = x == y
        elif op == 1:
            out.d[k] = x != y
        elif op == 2:
            out.d[k] = x < y
        elif op == 3:
            out.d[k] = x <= y
        elif op == 4:
            out.d[k] = x > y
        else:
            out.d[k] = x >= y
    return out


def _ail_tao_where_aa(m: _AilTAO, a: _AilTAO, b: _AilTAO) -> _AilTAO:
    n = len(a.d)
    if len(b.d) != n:
        _ail_ta_shapes(n, len(b.d))
    if len(m.d) != n:
        _ail_ta_shapes(len(m.d), n)
    out = _AilTAO(n)
    for k in range(n):
        if m.d[k]:
            out.d[k] = a.d[k]
        else:
            out.d[k] = b.d[k]
    return out


def _ail_tao_where_as(m: _AilTAO, a: _AilTAO, y: bool) -> _AilTAO:
    n = len(a.d)
    if len(m.d) != n:
        _ail_ta_shapes(len(m.d), n)
    out = _AilTAO(n)
    for k in range(n):
        if m.d[k]:
            out.d[k] = a.d[k]
        else:
            out.d[k] = y
    return out


def _ail_tao_where_sa(m: _AilTAO, x: bool, b: _AilTAO) -> _AilTAO:
    n = len(b.d)
    if len(m.d) != n:
        _ail_ta_shapes(len(m.d), n)
    out = _AilTAO(n)
    for k in range(n):
        if m.d[k]:
            out.d[k] = x
        else:
            out.d[k] = b.d[k]
    return out


def _ail_tao_any(a: _AilTAO) -> bool:
    for k in range(len(a.d)):
        if a.d[k]:
            return True
    return False


def _ail_tao_all(a: _AilTAO) -> bool:
    for k in range(len(a.d)):
        if not (a.d[k]):
            return False
    return True


def _ail_tao_take(a: _AilTAO, idx: _AilTAL) -> _AilTAO:
    n = len(a.d)
    out = _AilTAO(len(idx.d))
    for j in range(len(idx.d)):
        i = idx.d[j]
        k = i
        if k < 0:
            k = k + n
        if k < 0 or k >= n:
            _ail_ta_poserr(i, n)
        out.d[j] = a.d[k]
    return out


def _ail_tao_put(a: _AilTAO, idx: _AilTAL, src: _AilTAO):
    if len(src.d) != len(idx.d):
        raise ValueError("ail_array.put(): src has " + str(len(src.d)) + " elements but there are " + str(len(idx.d)) + " indices")
    s = list(src.d)
    for j in range(len(idx.d)):
        a.d[_ail_ta_pos(idx.d[j], len(a.d))] = s[j]


def _ail_tao_put_s(a: _AilTAO, idx: _AilTAL, x: bool):
    for j in range(len(idx.d)):
        a.d[_ail_ta_pos(idx.d[j], len(a.d))] = x


def _ail_tao_gstride(a: _AilTAO, offset: int, shape: list[int], strides: list[int]) -> _AilTAO:
    ps = _ail_ta_positions(len(a.d), offset, shape, strides, "gather_strided", "reads")
    out = _AilTAO(len(ps))
    for j in range(len(ps)):
        out.d[j] = a.d[ps[j]]
    return out


def _ail_tao_sstride(dst: _AilTAO, offset: int, shape: list[int], strides: list[int], src: _AilTAO):
    ps = _ail_ta_positions(len(dst.d), offset, shape, strides, "scatter_strided", "writes")
    if len(src.d) != len(ps):
        raise ValueError("ail_array.scatter_strided(): src has " + str(len(src.d)) + " elements but the shape has " + str(len(ps)))
    s = list(src.d)
    for j in range(len(ps)):
        dst.d[ps[j]] = s[j]


def _ail_tao_sstride_s(dst: _AilTAO, offset: int, shape: list[int], strides: list[int], x: bool):
    ps = _ail_ta_positions(len(dst.d), offset, shape, strides, "scatter_strided", "writes")
    for j in range(len(ps)):
        dst.d[ps[j]] = x


def _ail_tao_segbest(a: _AilTAO, offs: _AilTAL, smaller: bool, name: str) -> list[int]:
    ns = _ail_ta_segments(len(a.d), offs, name)
    res = [0] * ns
    for s in range(ns):
        lo = offs.d[s]
        hi = offs.d[s + 1]
        if lo == hi:
            raise ValueError("ail_array." + name + "(): segment " + str(s) + " is empty")
        best = lo
        for j in range(lo, hi):
            x = a.d[j]
            if j > lo:
                if smaller:
                    if (not x) and a.d[best]:
                        best = j
                else:
                    if (not a.d[best]) and x:
                        best = j
        res[s] = best
    return res


def _ail_tao_segmin(a: _AilTAO, offs: _AilTAL) -> _AilTAO:
    r = _ail_tao_segbest(a, offs, True, "segment_min")
    out = _AilTAO(len(r))
    for s in range(len(r)):
        out.d[s] = a.d[r[s]]
    return out


def _ail_tao_segmax(a: _AilTAO, offs: _AilTAL) -> _AilTAO:
    r = _ail_tao_segbest(a, offs, False, "segment_max")
    out = _AilTAO(len(r))
    for s in range(len(r)):
        out.d[s] = a.d[r[s]]
    return out


def _ail_tao_segargmin(a: _AilTAO, offs: _AilTAL) -> _AilTAL:
    r = _ail_tao_segbest(a, offs, True, "segment_argmin")
    out = _AilTAL(len(r))
    for s in range(len(r)):
        out.d[s] = r[s] - offs.d[s]
    return out


def _ail_tao_segargmax(a: _AilTAO, offs: _AilTAL) -> _AilTAL:
    r = _ail_tao_segbest(a, offs, False, "segment_argmax")
    out = _AilTAL(len(r))
    for s in range(len(r)):
        out.d[s] = r[s] - offs.d[s]
    return out


def _ail_tai_addchk(x: int, y: int, j: int, wrap: bool) -> int:
    v = x + y
    if v < -2147483648 or v > 2147483647:
        if wrap:
            return _ail_tai_wrap(v)
        raise OverflowError("int32 add overflow at index " + str(j))
    return v


def _ail_tal_addchk(x: int, y: int, j: int, wrap: bool) -> int:
    if wrap:
        return _ail_tal_wadd(x, y)
    return _ail_tal_one(x, y, 0, j)


def _ail_taf_segsum(a: _AilTAF, offs: _AilTAL) -> _AilTAF:
    ns = _ail_ta_segments(len(a.d), offs, "segment_sum")
    out = _AilTAF(ns)
    for s in range(ns):
        lo = offs.d[s]
        m = offs.d[s + 1] - lo
        seg = [0.0] * m
        for j in range(m):
            seg[j] = a.d[lo + j]
        out.d[s] = _ail_ta_canon(_ail_taf_fsum_s(seg))
    return out


def _ail_ta_isegsum(d: list[int], offs: _AilTAL, wrap: bool, name: str) -> _AilTAL:
    ns = _ail_ta_segments(len(d), offs, name)
    out = _AilTAL(ns)
    for s in range(ns):
        out.d[s] = _ail_ta_isum(d, offs.d[s], offs.d[s + 1], wrap, "int64 " + name + " overflow at segment " + str(s))
    return out


def _ail_tai_segsum(a: _AilTAI, offs: _AilTAL, wrap: bool, name: str) -> _AilTAL:
    return _ail_ta_isegsum(a.d, offs, wrap, name)


def _ail_tal_segsum(a: _AilTAL, offs: _AilTAL, wrap: bool, name: str) -> _AilTAL:
    return _ail_ta_isegsum(a.d, offs, wrap, name)


def _ail_tao_segsum(a: _AilTAO, offs: _AilTAL, wrap: bool, name: str) -> _AilTAL:
    ns = _ail_ta_segments(len(a.d), offs, name)
    out = _AilTAL(ns)
    for s in range(ns):
        c = 0
        for j in range(offs.d[s], offs.d[s + 1]):
            if a.d[j]:
                c = c + 1
        out.d[s] = c
    return out
