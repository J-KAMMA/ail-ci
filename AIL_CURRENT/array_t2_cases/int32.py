import ail_array as ta


def showi(label: str, a: ta.Array[ta.int32]):
    print(label, a, a.tobytes().hex())


def attempt(label: str, a: ta.Array[ta.int32], b: ta.Array[ta.int32], op: int):
    try:
        if op == 0:
            showi(label, a + b)
        elif op == 1:
            showi(label, a - b)
        elif op == 2:
            showi(label, a * b)
        elif op == 3:
            showi(label, a // b)
        else:
            showi(label, a % b)
    except OverflowError as exc:
        print(label, "OverflowError", exc)
    except ZeroDivisionError as exc:
        print(label, "ZeroDivisionError", exc)


def main():
    lo = -2147483648
    hi = 2147483647
    a = ta.array([0, 1, -1, 7, -7, hi, lo, hi - 1, lo + 1, 65536, -65536, 46340, 46341], ta.int32)
    b = ta.array([3, -3, 3, -2, 2, 1, 1, 0 + 1, -1, 65535, 32768, 46340, 46341], ta.int32)
    for op in range(5):
        attempt("op%d" % op, a, b, op)
    for op in range(5):
        attempt("small%d" % op, ta.array([5, -5, 9, 0], ta.int32), ta.array([3, 3, -4, 7], ta.int32), op)
    # first failing index
    c = ta.array([1, 2, hi, 4, hi], ta.int32)
    d = ta.array([1, 1, 1, 1, 1], ta.int32)
    attempt("first", c, d, 0)
    attempt("firstsub", ta.array([lo, 0, lo], ta.int32), d[0:3], 1)
    attempt("divzero", c, ta.array([1, 1, 0, 0, 1], ta.int32), 3)
    attempt("modzero", c, ta.array([1, 0, 1, 0, 1], ta.int32), 4)
    attempt("minus1", ta.array([lo, 5], ta.int32), ta.array([-1, -1], ta.int32), 3)
    attempt("minus1mod", ta.array([lo, 5], ta.int32), ta.array([-1, -1], ta.int32), 4)
    # in place: the prefix before the failing index is updated
    e = ta.array([1, 2, hi, 4, 5], ta.int32)
    try:
        e += 1
    except OverflowError as exc:
        print("iadd", exc)
    showi("e", e)
    e2 = ta.array([10, 20, 30], ta.int32)
    e2 *= 3
    showi("imul", e2)
    e2 //= 7
    showi("ifloordiv", e2)
    e2 %= 4
    showi("imod", e2)
    e2 -= ta.array([1, 1, 1], ta.int32)
    showi("isub", e2)
    # scalars
    showi("adds", a[0:5] + 5)
    showi("subs", a[0:5] - 5)
    showi("muls", a[0:5] * 3)
    showi("rsub", 100 - a[0:5])
    showi("rfloordiv", 100 // ta.array([1, 2, 3, -7], ta.int32))
    showi("rmod", 100 % ta.array([1, 2, 3, -7], ta.int32))
    showi("rmul", 3 * a[0:5])
    showi("bool", a[0:3] + True)
    try:
        print(a + 2147483648)
    except OverflowError as exc:
        print("scalar OverflowError", exc)
    try:
        print(a + (-2147483649))
    except OverflowError as exc:
        print("scalar OverflowError", exc)
    try:
        print(a // 0)
    except ZeroDivisionError as exc:
        print("scalar ZeroDivisionError", exc)
    # unary
    showi("neg", -a[0:5])
    showi("abs", abs(a[0:5]))
    try:
        print(-a)
    except OverflowError as exc:
        print("neg", exc)
    try:
        print(abs(ta.array([5, lo], ta.int32)))
    except OverflowError as exc:
        print("abs", exc)
    # wrapping / saturating
    showi("wadd", ta.wrapping_add(a, b))
    showi("wsub", ta.wrapping_sub(a, b))
    showi("wmul", ta.wrapping_mul(a, b))
    showi("sadd", ta.saturating_add(a, b))
    showi("ssub", ta.saturating_sub(a, b))
    showi("wadds", ta.wrapping_add(a, 1))
    showi("smuls", ta.saturating_sub(a, -1))
    # min/max/clip
    showi("minimum", ta.minimum(a, b))
    showi("maximum", ta.maximum(a, b))
    showi("minimum_s", ta.minimum(a, 5))
    showi("clip", ta.clip(a, -10, 10))
    print(ta.min(a), ta.max(a), ta.argmin(a), ta.argmax(a), ta.sum(a), ta.dot(a, b))
    m = ta.array([3, 1, 4, 1, 5, 9, 2, 6, 5, 3, 5, 9, 9], ta.int32)
    print(ta.min(m), ta.max(m), ta.argmin(m), ta.argmax(m))
    # stores
    s = ta.zeros(3, ta.int32)
    s[0] = hi
    s[1] = lo
    s[2] = True
    showi("s", s)
    for v in (hi + 1, lo - 1, 10 ** 12):
        try:
            s[0] = v
        except OverflowError as exc:
            print("store", exc)
    try:
        ta.full(2, hi + 1, ta.int32)
    except OverflowError as exc:
        print("full", exc)
    try:
        ta.array([1, 2, 3000000000], ta.int32)
    except OverflowError as exc:
        print("array", exc)
    showi("full", ta.full(3, -4, ta.int32))
    showi("arange", ta.arange(6, ta.int32))
    # casts
    print(a.astype(ta.f64))
    print(a.astype(ta.int32) == a, a.astype(ta.int32, 'nearest', 'wrap') == a)
    # bytes
    r = ta.frombytes(a.tobytes(), ta.int32)
    print(r == a, len(r))
    try:
        ta.frombytes(b'abc', ta.int32)
    except ValueError as exc:
        print("frombytes", exc)
    print(ta.frombytes(bytes([255, 255, 255, 255, 0, 0, 0, 128]), ta.int32))


main()
