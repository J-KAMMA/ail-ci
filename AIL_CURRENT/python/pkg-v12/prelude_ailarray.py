# -*- coding: utf-8 -*-
# prelude_ailarray.py -- `ail_array` (docs/design/TYPED_ARRAY.md, stage T2) for the dtypes f64 and int32, as Python source
# that the AIL compiler builds to native loops (ailarray.py rewrites the program onto these names and injects what it
# uses). It is plain Python 3.12 as well: test_ail_array_t2.py runs it under CPython against ail_array.py (the reference),
# so the two are compared op by op before any C is involved.
#
# An f64 array is a _AilTAF holding a list[float]; an int32 array is a _AilTAI holding a list[int]. The functions follow the
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
