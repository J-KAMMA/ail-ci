import ail_array as ta


def show(label: str, a: ta.Array[ta.int64]):
    print(label, a, a.tobytes().hex())


def attempt(label: str, a: ta.Array[ta.int64], b: ta.Array[ta.int64], op: int):
    try:
        if op == 0:
            show(label, a + b)
        elif op == 1:
            show(label, a - b)
        elif op == 2:
            show(label, a * b)
        elif op == 3:
            show(label, a // b)
        else:
            show(label, a % b)
    except OverflowError as exc:
        print(label, "OverflowError", exc)
    except ZeroDivisionError as exc:
        print(label, "ZeroDivisionError", exc)


def sums(vals: list[int]):
    v = ta.array(vals, ta.int64)
    w = ta.zeros(len(vals), ta.int64)
    for k in range(len(vals)):
        w[k] = (vals[k] * 3 + 1) % 100003
    try:
        print("sum", ta.sum(v))
    except OverflowError as exc:
        print("sum", "OverflowError", exc)
    print("wsum", ta.wrapping_sum(v), ta.wrapping_dot(v, w))


def main():
    lo = -9223372036854775807 - 1
    hi = 9223372036854775807
    # every pair of boundary values, one index per pair, so the first failing index is the pair that fails
    a = ta.array([0, 1, -1, 7, -7, hi, lo, hi - 1, lo + 1, 4294967296, -4294967296, 3037000499, 3037000500, 4611686018427387904],
                 ta.int64)
    b = ta.array([3, -3, 3, -2, 2, 1, 1, 1, -1, 4294967296, 2147483648, 3037000499, 3037000500, 2], ta.int64)
    for op in range(5):
        attempt("op%d" % op, a, b, op)
    for op in range(5):
        attempt("small%d" % op, ta.array([5, -5, 9, 0], ta.int64), ta.array([3, 3, -4, 7], ta.int64), op)
    # one overflowing pair at a time
    pairs_a = [hi, lo, lo, lo, hi, hi, 4611686018427387904, 4611686018427387904, -4611686018427387905, 3037000500, -3037000500]
    pairs_b = [1, -1, -1, 1, hi, -1, 2, -2, 2, 3037000500, 3037000500]
    for i in range(len(pairs_a)):
        x = ta.array([pairs_a[i]], ta.int64)
        y = ta.array([pairs_b[i]], ta.int64)
        for op in range(5):
            attempt("pair%d_%d" % (i, op), x, y, op)
    # first failing index
    c = ta.array([1, 2, hi, 4, hi], ta.int64)
    d = ta.array([1, 1, 1, 1, 1], ta.int64)
    attempt("first", c, d, 0)
    attempt("firstsub", ta.array([lo, 0, lo], ta.int64), d[0:3], 1)
    attempt("divzero", c, ta.array([1, 1, 0, 0, 1], ta.int64), 3)
    attempt("modzero", c, ta.array([1, 0, 1, 0, 1], ta.int64), 4)
    attempt("minus1", ta.array([lo, 5], ta.int64), ta.array([-1, -1], ta.int64), 3)
    attempt("minus1mod", ta.array([lo, 5], ta.int64), ta.array([-1, -1], ta.int64), 4)
    # in place: the prefix before the failing index is updated
    e = ta.array([1, 2, hi, 4, 5], ta.int64)
    try:
        e += 1
    except OverflowError as exc:
        print("iadd", exc)
    show("e", e)
    e2 = ta.array([10, 20, 30], ta.int64)
    e2 *= 3
    show("imul", e2)
    e2 //= 7
    show("ifloordiv", e2)
    e2 %= 4
    show("imod", e2)
    e2 -= ta.array([1, 1, 1], ta.int64)
    show("isub", e2)
    # scalars
    show("adds", a[0:5] + 5)
    show("subs", a[0:5] - 5)
    show("muls", a[0:5] * 3)
    show("rsub", 100 - a[0:5])
    show("rfloordiv", 100 // ta.array([1, 2, 3, -7], ta.int64))
    show("rmod", 100 % ta.array([1, 2, 3, -7], ta.int64))
    show("rmul", 3 * a[0:5])
    show("bool", a[0:3] + True)
    show("bigscalar", a[0:3] + 4611686018427387904)
    try:
        print(a + 1)
    except OverflowError as exc:
        print("scalar OverflowError", exc)
    try:
        print(a // 0)
    except ZeroDivisionError as exc:
        print("scalar ZeroDivisionError", exc)
    # unary
    show("neg", -a[0:5])
    show("abs", abs(a[0:5]))
    try:
        print(-a)
    except OverflowError as exc:
        print("neg", exc)
    try:
        print(abs(ta.array([5, lo], ta.int64)))
    except OverflowError as exc:
        print("abs", exc)
    # wrapping / saturating
    show("wadd", ta.wrapping_add(a, b))
    show("wsub", ta.wrapping_sub(a, b))
    show("wmul", ta.wrapping_mul(a, b))
    show("sadd", ta.saturating_add(a, b))
    show("ssub", ta.saturating_sub(a, b))
    show("wadds", ta.wrapping_add(a, 1))
    show("wmuls", ta.wrapping_mul(a, 3037000500))
    show("ssubs", ta.saturating_sub(a, -1))
    show("wneg", ta.wrapping_neg(a))
    show("wabs", ta.wrapping_abs(a))
    show("wfloordiv", ta.wrapping_floordiv(a, ta.array([3, -3, 3, -2, 2, 1, 1, 1, -1, 2, 2, -1, -1, -1], ta.int64)))
    show("wfloordiv_s", ta.wrapping_floordiv(a, -1))
    show("wfloordiv_s2", ta.wrapping_floordiv(a, 7))
    try:
        ta.wrapping_floordiv(a, 0)
    except ZeroDivisionError as exc:
        print("wfloordiv0", exc)
    # min/max/clip, reductions
    show("minimum", ta.minimum(a, b))
    show("maximum", ta.maximum(a, b))
    show("minimum_s", ta.minimum(a, 5))
    show("clip", ta.clip(a, -10, 10))
    print(ta.min(a), ta.max(a), ta.argmin(a), ta.argmax(a), ta.wrapping_sum(a), ta.wrapping_dot(a, b))
    m = ta.array([3, 1, 4, 1, 5, 9, 2, 6, 5, 3, 5, 9, 9], ta.int64)
    print(ta.min(m), ta.max(m), ta.argmin(m), ta.argmax(m), ta.sum(m))
    sums([hi, 1])
    sums([hi, hi, hi])
    sums([lo, lo])
    sums([lo, -1])
    sums([hi, hi, lo, lo])
    sums([4611686018427387904, 4611686018427387904, 4611686018427387904, 4611686018427387904, 4611686018427387904])
    nothing: list[int] = []
    sums(nothing)
    sums([hi, 1, -1])
    try:
        ta.min(ta.zeros(0, ta.int64))
    except ValueError as exc:
        print("min", exc)
    # stores
    s = ta.zeros(3, ta.int64)
    s[0] = hi
    s[1] = lo
    s[2] = True
    show("s", s)
    show("full", ta.full(3, -4, ta.int64))
    show("arange", ta.arange(6, ta.int64))
    try:
        s[0] = 1.5
    except TypeError as exc:
        print("float store", exc)
    try:
        ta.arange(-1, ta.int64)
    except ValueError as exc:
        print("arange", exc)
    # bytes
    r = ta.frombytes(a.tobytes(), ta.int64)
    print(r == a, len(r))
    try:
        ta.frombytes(b'abcdefg', ta.int64)
    except ValueError as exc:
        print("frombytes", exc)
    print(ta.frombytes(bytes([255, 255, 255, 255, 255, 255, 255, 127, 0, 0, 0, 0, 0, 0, 0, 128, 1, 0, 0, 0, 0, 0, 0, 0]), ta.int64))
    # indexing and slices
    print(a[0], a[-1], a[13], a[2:9:3], a[::-1][0:3], len(a))
    try:
        print(a[14])
    except IndexError as exc:
        print("index", exc)
    t = ta.zeros(6, ta.int64)
    t[1:6:2] = ta.array([hi, lo, 7], ta.int64)
    show("setslice", t)
    for v in a[0:4]:
        print(v)
    print(a.tolist()[5], list(a)[6], a == a, a == b, a != b)
    # int64 against other dtypes
    f = a.astype(ta.f64)
    print(f)
    print(a == f, f == a)
    try:
        print(a + f)
    except TypeError as exc:
        print("mix", exc)
    try:
        print(a + 0.5)
    except TypeError as exc:
        print("float scalar", exc)


main()
