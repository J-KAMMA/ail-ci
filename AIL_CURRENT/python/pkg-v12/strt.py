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
