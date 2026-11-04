"""The runtime of `statistics` (library batch 4) over lists of int, written in the Python subset the compiler
builds; plain Python, so the test suite runs the same functions against the `statistics` module.

Exact like CPython where CPython is exact: sums, squares and the fractions of the variances are integers
here (the language's ints are 64-bit, an overflow is an OverflowError, never a wrong digit), and the square
root of a fraction is CPython's own algorithm (round-to-odd integer square root, then one rounding) done on
wide integers kept as lists of 24-bit limbs. A fraction whose reduced numerator or denominator is 2**53 or
more cannot be turned into the correctly rounded float by one division here: that is a RuntimeError.
"""


# -- core:
def sorted_ints(xs: list[int]) -> list[int]:
    out = sorted(xs)
    return out


def total(xs: list[int]) -> int:
    t = 0
    for x in xs:
        t += x
    return t


def gcd(a: int, b: int) -> int:
    x = a if a >= 0 else -a
    y = b if b >= 0 else -b
    while y != 0:
        r = x % y
        x = y
        y = r
    return x


def need(n: int, least: int, what: str) -> None:
    if n < least:
        if least == 1:
            raise ValueError(what + " requires at least one data point")
        raise ValueError(what + " requires at least two data points")


def frac_float(num: int, den: int) -> float:
    """num / den correctly rounded (den > 0); exact when both are below 2**53."""
    g = gcd(num, den)
    a = num // g
    b = den // g
    if a >= 9007199254740992 or a <= -9007199254740992 or b >= 9007199254740992:
        raise RuntimeError("statistics: a fraction with a numerator or denominator of 2**53 or more is not built (the correctly rounded quotient needs wide integers)")
    return a / b


def mean_is_int(xs: list[int]) -> bool:
    need(len(xs), 1, "mean")
    return total(xs) % len(xs) == 0


def mean_text(xs: list[int]) -> str:
    need(len(xs), 1, "mean")
    t = total(xs)
    n = len(xs)
    if t % n == 0:
        return str(t // n)
    return str(frac_float(t, n))


def mean_float(xs: list[int]) -> float:
    need(len(xs), 1, "mean")
    return frac_float(total(xs), len(xs))


def fmean(xs: list[int]) -> float:
    n = len(xs)
    if n == 0:
        raise ValueError("fmean requires at least one data point")
    floats: list[float] = []
    for x in xs:
        floats.append(float(x))
    return fsum_floats(floats) / n


def fsum_floats_mean(xs: list[float]) -> float:
    n = len(xs)
    if n == 0:
        raise ValueError("fmean requires at least one data point")
    return fsum_floats(xs) / n


def fsum_floats(xs: list[float]) -> float:
    """math.fsum: exact partial sums (Shewchuk), rounded once."""
    partials: list[float] = []
    for x in xs:
        v = x
        i = 0
        for j in range(len(partials)):
            y = partials[j]
            if abs(v) < abs(y):
                tmp = v
                v = y
                y = tmp
            hi = v + y
            lo = y - (hi - v)
            if lo != 0.0:
                partials[i] = lo
                i += 1
            v = hi
        while len(partials) > i:
            partials.pop()
        partials.append(v)
    n = len(partials)
    if n == 0:
        return 0.0
    hi = partials[n - 1]
    n -= 1
    lo = 0.0
    while n > 0:
        x = hi
        y = partials[n - 1]
        n -= 1
        hi = x + y
        yr = hi - x
        lo = y - yr
        if lo != 0.0:
            break
    if n > 0 and ((lo < 0.0 and partials[n - 1] < 0.0) or (lo > 0.0 and partials[n - 1] > 0.0)):
        y = lo * 2.0
        x = hi + y
        yr = x - hi
        if y == yr:
            hi = x
    return hi


def median_is_int(xs: list[int]) -> bool:
    need(len(xs), 1, "median")
    return len(xs) % 2 == 1


def median_text(xs: list[int]) -> str:
    n = len(xs)
    if n == 0:
        raise ValueError("no median for empty data")
    d = sorted_ints(xs)
    if n % 2 == 1:
        return str(d[n // 2])
    i = n // 2
    return str((d[i - 1] + d[i]) / 2)


def median_float(xs: list[int]) -> float:
    n = len(xs)
    if n == 0:
        raise ValueError("no median for empty data")
    d = sorted_ints(xs)
    if n % 2 == 1:
        return float(d[n // 2])
    i = n // 2
    return (d[i - 1] + d[i]) / 2


def median_low(xs: list[int]) -> int:
    n = len(xs)
    if n == 0:
        raise ValueError("no median for empty data")
    d = sorted_ints(xs)
    if n % 2 == 1:
        return d[n // 2]
    return d[n // 2 - 1]


def median_high(xs: list[int]) -> int:
    n = len(xs)
    if n == 0:
        raise ValueError("no median for empty data")
    d = sorted_ints(xs)
    return d[n // 2]


def mode_int(xs: list[int]) -> int:
    n = len(xs)
    if n == 0:
        raise ValueError("no mode for empty data")
    counts: dict[int, int] = {}
    order: list[int] = []
    for x in xs:
        if x in counts:
            counts[x] += 1
        else:
            counts[x] = 1
            order.append(x)
    best = order[0]
    for y in order:
        if counts[y] > counts[best]:
            best = y
    return best


def multimode_int(xs: list[int]) -> list[int]:
    counts: dict[int, int] = {}
    order: list[int] = []
    for x in xs:
        if x in counts:
            counts[x] += 1
        else:
            counts[x] = 1
            order.append(x)
    out: list[int] = []
    top = 0
    for y in order:
        if counts[y] > top:
            top = counts[y]
    for z in order:
        if counts[z] == top:
            out.append(z)
    return out


def mode_str(xs: list[str]) -> str:
    n = len(xs)
    if n == 0:
        raise ValueError("no mode for empty data")
    counts: dict[str, int] = {}
    order: list[str] = []
    for x in xs:
        if x in counts:
            counts[x] += 1
        else:
            counts[x] = 1
            order.append(x)
    best = order[0]
    for y in order:
        if counts[y] > counts[best]:
            best = y
    return best


def multimode_str(xs: list[str]) -> list[str]:
    counts: dict[str, int] = {}
    order: list[str] = []
    for x in xs:
        if x in counts:
            counts[x] += 1
        else:
            counts[x] = 1
            order.append(x)
    out: list[str] = []
    top = 0
    for y in order:
        if counts[y] > top:
            top = counts[y]
    for z in order:
        if counts[z] == top:
            out.append(z)
    return out


# -- floats (library batch 5): the functions of the module that need no exact fractions
def sorted_floats(xs: list[float]) -> list[float]:
    out: list[float] = []
    for x in xs:
        out.append(x)
    out.sort()
    return out


def median_f(xs: list[float]) -> float:
    n = len(xs)
    if n == 0:
        raise ValueError("no median for empty data")
    d = sorted_floats(xs)
    if n % 2 == 1:
        return d[n // 2]
    i = n // 2
    return (d[i - 1] + d[i]) / 2


def median_low_f(xs: list[float]) -> float:
    n = len(xs)
    if n == 0:
        raise ValueError("no median for empty data")
    d = sorted_floats(xs)
    if n % 2 == 1:
        return d[n // 2]
    return d[n // 2 - 1]


def median_high_f(xs: list[float]) -> float:
    n = len(xs)
    if n == 0:
        raise ValueError("no median for empty data")
    d = sorted_floats(xs)
    return d[n // 2]


def runs_f(xs: list[float], want_first: bool) -> list[int]:
    """For each position: how many times its value occurs (want_first False), or 1 when it is the first
    occurrence of its value and 0 otherwise (want_first True). Values are told apart by their repr (the
    shortest text of a double; 0.0 and -0.0 are one value, as for == ; every nan is one value, unlike CPython)."""
    counts: dict[str, int] = {}
    for x in xs:
        k = str(x + 0.0)
        if k in counts:
            counts[k] += 1
        else:
            counts[k] = 1
    out: list[int] = []
    seen: dict[str, int] = {}
    for y in xs:
        k2 = str(y + 0.0)
        if want_first:
            if k2 in seen:
                out.append(0)
            else:
                seen[k2] = 1
                out.append(1)
        else:
            out.append(counts[k2])
    return out


def mode_f(xs: list[float]) -> float:
    n = len(xs)
    if n == 0:
        raise ValueError("no mode for empty data")
    counts = runs_f(xs, False)
    best = 0
    for i in range(n):
        if counts[i] > counts[best]:
            best = i
    return xs[best]


def multimode_f(xs: list[float]) -> list[float]:
    counts = runs_f(xs, False)
    first = runs_f(xs, True)
    top = 0
    for c in counts:
        if c > top:
            top = c
    out: list[float] = []
    for i in range(len(xs)):
        if first[i] == 1 and counts[i] == top:
            out.append(xs[i])
    return out


# -- variance: needs core
def ss_numerator(xs: list[int]) -> int:
    """n * sum(x*x) - sum(x)**2 : the sum of squared deviations is this over n."""
    n = len(xs)
    sx = 0
    sxx = 0
    for x in xs:
        sx += x
        sxx += x * x
    return n * sxx - sx * sx


def var_num(xs: list[int], sample: bool) -> int:
    return ss_numerator(xs)


def var_den(xs: list[int], sample: bool) -> int:
    n = len(xs)
    if sample:
        return n * (n - 1)
    return n * n


def variance_is_int(xs: list[int], sample: bool) -> bool:
    check_var(len(xs), sample, "variance")
    num = var_num(xs, sample)
    den = var_den(xs, sample)
    return num % den == 0


def check_var(n: int, sample: bool, what: str) -> None:
    if sample:
        if n < 2:
            raise ValueError(what + " requires at least two data points")
    else:
        if n < 1:
            raise ValueError("p" + what + " requires at least one data point")


def variance_text(xs: list[int], sample: bool) -> str:
    check_var(len(xs), sample, "variance")
    num = var_num(xs, sample)
    den = var_den(xs, sample)
    if num % den == 0:
        return str(num // den)
    return str(frac_float(num, den))


def variance_float(xs: list[int], sample: bool) -> float:
    check_var(len(xs), sample, "variance")
    return frac_float(var_num(xs, sample), var_den(xs, sample))


# wide non-negative integers: little-endian limbs of 24 bits
def w_from(x: int) -> list[int]:
    out: list[int] = []
    y = x
    while y > 0:
        out.append(y % 16777216)
        y = y // 16777216
    return out


def w_trim(a: list[int]) -> list[int]:
    out: list[int] = []
    for v in a:
        out.append(v)
    while len(out) > 0 and out[len(out) - 1] == 0:
        out.pop()
    return out


def w_mul(a: list[int], b: list[int]) -> list[int]:
    if len(a) == 0 or len(b) == 0:
        return []
    out: list[int] = []
    for k in range(len(a) + len(b)):
        out.append(0)
    for i in range(len(a)):
        carry = 0
        for j in range(len(b)):
            cur = out[i + j] + a[i] * b[j] + carry
            out[i + j] = cur % 16777216
            carry = cur // 16777216
        k = i + len(b)
        while carry > 0:
            cur = out[k] + carry
            out[k] = cur % 16777216
            carry = cur // 16777216
            k += 1
    return w_trim(out)


def w_shl(a: list[int], bits: int) -> list[int]:
    if len(a) == 0:
        return []
    whole = bits // 24
    part = bits % 24
    out: list[int] = []
    for i in range(whole):
        out.append(0)
    carry = 0
    for v in a:
        cur = v * (1 << part) + carry
        out.append(cur % 16777216)
        carry = cur // 16777216
    if carry > 0:
        out.append(carry)
    return out


def w_cmp(a: list[int], b: list[int]) -> int:
    if len(a) != len(b):
        if len(a) < len(b):
            return -1
        return 1
    i = len(a) - 1
    while i >= 0:
        if a[i] != b[i]:
            if a[i] < b[i]:
                return -1
            return 1
        i -= 1
    return 0


def bit_len(x: int) -> int:
    n = 0
    y = x
    while y > 0:
        y = y >> 1
        n += 1
    return n


def sqrt_of_frac(n: int, m: int) -> float:
    """CPython's _float_sqrt_of_frac(n, m): the correctly rounded sqrt(n / m) (n >= 0, m > 0)."""
    if n == 0:
        return 0.0
    g = gcd(n, m)
    a = n // g
    b = m // g
    q = (bit_len(a) - bit_len(b) - 109) // 2
    if q >= 0:
        raise RuntimeError("statistics: the square root of a fraction this large is not built")
    shift = -2 * q
    big_n = w_shl(w_from(a), shift)
    wb = w_from(b)
    lo = 0
    hi = 1 << 58
    # the largest r with b * r * r <= a * 2**shift
    while lo < hi:
        mid = (lo + hi + 1) // 2
        wr = w_from(mid)
        prod = w_mul(w_mul(wr, wr), wb)
        if w_cmp(prod, big_n) <= 0:
            lo = mid
        else:
            hi = mid - 1
    r = lo
    wr = w_from(r)
    exact = w_cmp(w_mul(w_mul(wr, wr), wb), big_n) == 0
    odd = r
    if not exact:
        odd = r | 1
    return odd / (1 << (-q))


def stdev_float(xs: list[int], sample: bool) -> float:
    n = len(xs)
    if sample:
        if n < 2:
            raise ValueError("stdev requires at least two data points")
    else:
        if n < 1:
            raise ValueError("pstdev requires at least one data point")
    return sqrt_of_frac(var_num(xs, sample), var_den(xs, sample))


# -- quantiles, covariance and correlation (library batch 4)
def to_floats(xs: list[int]) -> list[float]:
    out: list[float] = []
    for x in xs:
        out.append(float(x))
    return out


def quantiles_int(xs: list[int], n: int, method: str) -> list[float]:
    if n < 1:
        raise ValueError("n must be at least 1")
    d = sorted_ints(xs)
    ld = len(d)
    if ld < 2:
        raise ValueError("must have at least two data points")
    if method != "inclusive" and method != "exclusive":
        raise ValueError("Unknown method: " + repr(method))
    out: list[float] = []
    if method == "inclusive":
        m = ld - 1
        for i in range(1, n):
            j = i * m // n
            delta = i * m - j * n
            out.append((d[j] * (n - delta) + d[j + 1] * delta) / n)
        return out
    m = ld + 1
    for i in range(1, n):
        j = i * m // n
        if j < 1:
            j = 1
        if j > ld - 1:
            j = ld - 1
        delta = i * m - j * n
        out.append((d[j - 1] * (n - delta) + d[j] * delta) / n)
    return out


def quantiles_f(xs: list[float], n: int, method: str) -> list[float]:
    if n < 1:
        raise ValueError("n must be at least 1")
    d = sorted_floats(xs)
    ld = len(d)
    if ld < 2:
        raise ValueError("must have at least two data points")
    if method != "inclusive" and method != "exclusive":
        raise ValueError("Unknown method: " + repr(method))
    out: list[float] = []
    if method == "inclusive":
        m = ld - 1
        for i in range(1, n):
            j = i * m // n
            delta = i * m - j * n
            out.append((d[j] * (n - delta) + d[j + 1] * delta) / n)
        return out
    m = ld + 1
    for i in range(1, n):
        j = i * m // n
        if j < 1:
            j = 1
        if j > ld - 1:
            j = ld - 1
        delta = i * m - j * n
        out.append((d[j - 1] * (n - delta) + d[j] * delta) / n)
    return out


def dl_sum(a: float, b: float) -> list[float]:
    """CPython's error-free two-sum: [rounded a + b, exact error]."""
    x = a + b
    z = x - a
    y = (a - (x - z)) + (b - z)
    return [x, y]


def dl_product(a: float, b: float) -> list[float]:
    """The rounded product and its exact error (CPython's dl_mul with fma).  The Dekker split is
    done on operands scaled by a power of two, so neither the split nor the product overflows or
    loses the low bits when a or b is near the ends of the double range."""
    p = a * b
    if p - p != 0.0:
        return [p, 0.0]
    aa = a
    ea = 0
    if aa != 0.0:
        while abs(aa) >= 1.0:
            aa = aa * 0.5
            ea += 1
        while abs(aa) < 0.5:
            aa = aa * 2.0
            ea -= 1
    bb = b
    eb = 0
    if bb != 0.0:
        while abs(bb) >= 1.0:
            bb = bb * 0.5
            eb += 1
        while abs(bb) < 0.5:
            bb = bb * 2.0
            eb -= 1
    ps = aa * bb
    split = 134217729.0
    ca = split * aa
    ahi = ca - (ca - aa)
    alo = aa - ahi
    cb = split * bb
    bhi = cb - (cb - bb)
    blo = bb - bhi
    es = ((ahi * bhi - ps) + ahi * blo + alo * bhi) + alo * blo
    shift = ea + eb
    pscaled = p
    if shift > 0:
        for _ in range(shift):
            pscaled = pscaled * 0.5
    else:
        for _ in range(-shift):
            pscaled = pscaled * 2.0
    err = (ps - pscaled) + es
    if shift > 0:
        for _ in range(shift):
            err = err * 2.0
    else:
        for _ in range(-shift):
            err = err * 0.5
    return [p, err]


def tl_to_d(hi: float, lo: float, tiny: float) -> float:
    last = dl_sum(lo, hi)
    return tiny + last[1] + last[0]


def sumprod_floats(xs: list[float], ys: list[float]) -> float:
    """math.sumprod over floats: CPython's TripleLength compensated sum of error-free products.
    A non-finite product stops the compensated path, as in CPython, and the rest is ordinary
    float multiplication and addition (so an overflowing product gives inf or nan, not nan from
    an overflowing Dekker split)."""
    total_hi = 0.0
    total_lo = 0.0
    total_tiny = 0.0
    naive = 0.0
    exact = True
    for i in range(len(xs)):
        a = xs[i]
        b = ys[i]
        if exact:
            pr = dl_product(a, b)
            p = pr[0]
            err = pr[1]
            if p - p != 0.0:
                naive = tl_to_d(total_hi, total_lo, total_tiny)
                exact = False
            else:
                sm = dl_sum(total_hi, p)
                r1 = dl_sum(total_lo, err)
                r2 = dl_sum(r1[0], sm[1])
                if sm[0] - sm[0] != 0.0:
                    naive = tl_to_d(total_hi, total_lo, total_tiny)
                    exact = False
                else:
                    total_hi = sm[0]
                    total_lo = r2[0]
                    total_tiny = total_tiny + r1[1] + r2[1]
        if not exact:
            naive = naive + a * b
    if exact:
        return tl_to_d(total_hi, total_lo, total_tiny)
    return naive


def covariance_f(xs: list[float], ys: list[float]) -> float:
    n = len(xs)
    if len(ys) != n:
        raise ValueError("covariance requires that both inputs have same number of data points")
    if n < 2:
        raise ValueError("covariance requires at least two data points")
    xbar = fsum_floats(xs) / n
    ybar = fsum_floats(ys) / n
    dx: list[float] = []
    dy: list[float] = []
    for i in range(n):
        dx.append(xs[i] - xbar)
        dy.append(ys[i] - ybar)
    return sumprod_floats(dx, dy) / (n - 1)


def correlation_f(xs: list[float], ys: list[float], method: str) -> float:
    n = len(xs)
    if len(ys) != n:
        raise ValueError("correlation requires that both inputs have same number of data points")
    if n < 2:
        raise ValueError("correlation requires at least two data points")
    if method != "linear":
        raise ValueError("Unknown method: " + repr(method))
    xbar = fsum_floats(xs) / n
    ybar = fsum_floats(ys) / n
    dx: list[float] = []
    dy: list[float] = []
    for i in range(n):
        dx.append(xs[i] - xbar)
        dy.append(ys[i] - ybar)
    sxy = sumprod_floats(dx, dy)
    sxx = sumprod_floats(dx, dx)
    syy = sumprod_floats(dy, dy)
    if sxx * syy == 0.0:
        raise ValueError("at least one of the inputs is constant")
    return sxy / (sxx * syy) ** 0.5


def fmean_weights(xs: list[float], ws: list[float]) -> float:
    if len(xs) != len(ws):
        raise ValueError("data and weights must be the same length")
    den = fsum_floats(ws)
    if den == 0.0:
        raise ValueError("sum of weights must be non-zero")
    return sumprod_floats(xs, ws) / den


def fmean_weights_int(xs: list[int], ws: list[int]) -> float:
    """Weighted fmean over ints: the product sum is an exact int like math.sumprod, then CPython's
    int / float division rounds it once; the denominator is fsum of the weights (each as a float)."""
    if len(xs) != len(ws):
        raise ValueError("data and weights must be the same length")
    den = fsum_floats(to_floats(ws))
    if den == 0.0:
        raise ValueError("sum of weights must be non-zero")
    num = 0
    for i in range(len(xs)):
        num += xs[i] * ws[i]
    return float(num) / den


# -- the given centre (xbar= / mu=), geometric and harmonic mean, linear regression (job stats2)
def ratio_float(num: int, den: int) -> float:
    """num / den correctly rounded, for any two int64 values (den > 0), as CPython's int true division
    and float(Fraction).  The quotient is scaled to 55 bits, the dropped bits kept as a sticky remainder."""
    if num == 0:
        return 0.0
    neg = num < 0
    a = num
    if neg:
        a = -a
    e = 0
    q = a // den
    r = a % den
    while q >= 36028797018963968:
        if q % 2 == 1:
            r = 1
        q = q // 2
        e = e + 1
    while q < 18014398509481984:
        if r >= den - r:
            q = q * 2 + 1
            r = r - (den - r)
        else:
            q = q * 2
            r = r + r
        e = e - 1
    low = q % 4
    q = q // 4
    e = e + 2
    if low > 2 or (low == 2 and (r != 0 or q % 2 == 1)):
        q = q + 1
    x = float(q)
    while e > 0:
        x = x * 2.0
        e = e - 1
    while e < 0:
        x = x / 2.0
        e = e + 1
    if neg:
        x = -x
    return x


def ss_centre(xs: list[int], c: int) -> int:
    """sum((x - c)**2), the exact numerator of variance(xs, xbar=c) (CPython's _ss with c given)."""
    total = 0
    for x in xs:
        d = x - c
        total += d * d
    return total


def variance_c_text(xs: list[int], c: int, sample: bool) -> str:
    check_var(len(xs), sample, "variance")
    num = ss_centre(xs, c)
    den = len(xs) - 1 if sample else len(xs)
    if num % den == 0:
        return str(num // den)
    return str(ratio_float(num, den))


def variance_c_float(xs: list[int], c: int, sample: bool) -> float:
    check_var(len(xs), sample, "variance")
    num = ss_centre(xs, c)
    den = len(xs) - 1 if sample else len(xs)
    return ratio_float(num, den)


def stdev_c(xs: list[int], c: int, sample: bool) -> float:
    if sample:
        if len(xs) < 2:
            raise ValueError("stdev requires at least two data points")
    else:
        if len(xs) < 1:
            raise ValueError("pstdev requires at least one data point")
    num = ss_centre(xs, c)
    den = len(xs) - 1 if sample else len(xs)
    return sqrt_of_frac(num, den)


def geometric_mean_int(xs: list[int]) -> float:
    n = len(xs)
    message = "geometric mean requires a non-empty dataset containing positive numbers"
    if n == 0:
        raise ValueError(message)
    for x in xs:
        if x <= 0:
            raise ValueError(message)
    logs: list[float] = []
    for x in xs:
        logs.append(math.log(float(x)))
    return math.exp(fsum_floats(logs) / n)


def harmonic_mean_int(xs: list[int]) -> float:
    """n / (the exact sum of the floats 1/x), rounded once: CPython's harmonic_mean over ints.
    The lowering builds this only for a literal positive list whose scaled sum fits int64."""
    n = len(xs)
    if n < 1:
        raise ValueError("harmonic_mean requires at least one data point")
    ms: list[int] = []
    es: list[int] = []
    for x in xs:
        if x < 0:
            raise ValueError("harmonic mean does not support negative values")
        if x == 0:
            return 0.0
        t = ratio_float(1, x)
        e = 0
        while t != float(int(t)):
            t = t * 2.0
            e += 1
        ms.append(int(t))
        es.append(e)
    big = 0
    for e in es:
        if e > big:
            big = e
    s = 0
    for i in range(n):
        s += ms[i] << (big - es[i])
    shift = 0
    while s % 2 == 0:
        s = s // 2
        shift += 1
    if big >= shift:
        num = n << (big - shift)
        den = s
    else:
        num = n
        den = s << (shift - big)
    return ratio_float(num, den)


def linear_regression_int(xs: list[int], ys: list[int]) -> list[float]:
    """[slope, intercept] for ordinary least squares, CPython 3.12's float algorithm (fsum, sumprod)."""
    n = len(xs)
    if len(ys) != n:
        raise ValueError("linear regression requires that both inputs have same number of data points")
    if n < 2:
        raise ValueError("linear regression requires at least two data points")
    fx = to_floats(xs)
    fy = to_floats(ys)
    xbar = fsum_floats(fx) / n
    ybar = fsum_floats(fy) / n
    dx: list[float] = []
    dy: list[float] = []
    for i in range(n):
        dx.append(fx[i] - xbar)
        dy.append(fy[i] - ybar)
    sxy = sumprod_floats(dx, dy) + 0.0
    sxx = sumprod_floats(dx, dx)
    if sxx == 0.0:
        raise ValueError("x is constant")
    slope = sxy / sxx
    return [slope, ybar - slope * xbar]


def linear_regression_prop(xs: list[int], ys: list[int]) -> list[float]:
    """[slope, 0.0] through the origin; the int products are exact like math.sumprod, then rounded."""
    n = len(xs)
    if len(ys) != n:
        raise ValueError("linear regression requires that both inputs have same number of data points")
    if n < 2:
        raise ValueError("linear regression requires at least two data points")
    sxy = 0
    sxx = 0
    for i in range(n):
        sxy += xs[i] * ys[i]
        sxx += xs[i] * xs[i]
    if sxx == 0:
        raise ValueError("x is constant")
    slope = (float(sxy) + 0.0) / float(sxx)
    return [slope, 0.0]


def linear_repr(fit: list[float]) -> str:
    return "LinearRegression(slope=" + str(fit[0]) + ", intercept=" + str(fit[1]) + ")"
