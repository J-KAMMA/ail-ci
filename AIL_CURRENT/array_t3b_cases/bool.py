import ail_array as ta


def showo(label: str, a: ta.Array[ta.bool_]):
    print(label, a, a.tobytes().hex())


def showf(label: str, a: ta.Array[ta.f64]):
    print(label, a, a.tobytes().hex())


def showl(label: str, a: ta.Array[ta.int64]):
    print(label, a, a.tobytes().hex())


def main():
    nan = float("nan")
    inf = float("inf")
    t = ta.array([True, False, True, False], ta.bool_)
    u = ta.array([True, True, False, False], ta.bool_)
    showo("t", t)
    showo("zeros", ta.zeros(3, ta.bool_))
    showo("full", ta.full(3, True, ta.bool_))
    showo("fullint", ta.full(2, 5, ta.bool_))
    showo("fromints", ta.array([0, 1, 2, -3], ta.bool_))
    print(len(t), t[0], t[1], t[-1], t[1:4:2], t[::-1], t.tolist(), list(t))
    try:
        print(t[4])
    except IndexError as exc:
        print("index", exc)
    # logic
    showo("and", ta.logical_and(t, u))
    showo("or", ta.logical_or(t, u))
    showo("xor", ta.logical_xor(t, u))
    showo("not", ta.logical_not(t))
    showo("and_s", ta.logical_and(t, True))
    showo("or_s", ta.logical_or(t, False))
    showo("xor_i", ta.logical_xor(t, 3))
    # no arithmetic on bool_
    try:
        print(t + u)
    except TypeError as exc:
        print("add", exc)
    try:
        print(t * 2)
    except TypeError as exc:
        print("mul", exc)
    try:
        print(-t)
    except TypeError as exc:
        print("neg", exc)
    try:
        print(abs(t))
    except TypeError as exc:
        print("abs", exc)
    try:
        print(2 - t)
    except TypeError as exc:
        print("rsub", exc)
    try:
        print(ta.wrapping_add(t, u))
    except TypeError as exc:
        print("wadd", exc)
    try:
        print(ta.dot(t, u))
    except TypeError as exc:
        print("dot", exc)
    try:
        print(ta.sqrt(t))
    except TypeError as exc:
        print("sqrt", exc)
    try:
        print(ta.logical_and(t, 1.5))
    except TypeError as exc:
        print("logical float", exc)
    f0 = ta.array([1.0, 2.0, 3.0, 4.0], ta.f64)
    try:
        print(ta.logical_and(f0, t))
    except TypeError as exc:
        print("logical on float", exc)
    # stores
    s = ta.zeros(4, ta.bool_)
    s[0] = True
    s[1] = 7
    s[2] = False
    showo("store", s)
    try:
        s[3] = 0.5
    except TypeError as exc:
        print("float store", exc)
    s[1:3] = ta.array([False, True], ta.bool_)
    showo("setslice", s)
    # reductions
    print(ta.sum(t), ta.sum(ta.zeros(0, ta.bool_)), ta.min(t), ta.max(t), ta.argmin(t), ta.argmax(t), ta.any(t), ta.all(t))
    print(ta.any(ta.zeros(0, ta.bool_)), ta.all(ta.zeros(0, ta.bool_)), ta.any(ta.zeros(3, ta.bool_)), ta.all(ta.full(3, True, ta.bool_)))
    try:
        ta.max(ta.zeros(0, ta.bool_))
    except ValueError as exc:
        print("max", exc)
    showo("minimum", ta.minimum(t, u))
    showo("maximum", ta.maximum(t, u))
    showo("maximum_s", ta.maximum(t, False))
    # comparisons on floats (IEEE), ints and bool
    x = ta.array([nan, 0.0, -0.0, 1.0, 0.1, inf, -inf, 2.5], ta.f64)
    y = ta.array([nan, -0.0, 0.0, 1.0, 0.1000000000000001, inf, inf, -2.5], ta.f64)
    showo("eq", ta.eq(x, y))
    showo("ne", ta.ne(x, y))
    showo("lt", ta.lt(x, y))
    showo("le", ta.le(x, y))
    showo("gt", ta.gt(x, y))
    showo("ge", ta.ge(x, y))
    showo("eq_s", ta.eq(x, 0.1))
    showo("lt_s", ta.lt(x, 1))
    showo("ge_s", ta.ge(x, nan))
    print(ta.any(x), ta.all(x), ta.any(ta.array([0.0, -0.0, nan], ta.f64)), ta.all(ta.array([1.0, nan], ta.f64)))
    hi = 9223372036854775807
    lo = -9223372036854775807 - 1
    p = ta.array([lo, -1, 0, 1, hi, 5, 5, -5], ta.int64)
    q = ta.array([hi, -1, 0, 2, hi, -5, 5, 5], ta.int64)
    showo("ieq", ta.eq(p, q))
    showo("ilt", ta.lt(p, q))
    showo("ige", ta.ge(p, q))
    showo("ine_s", ta.ne(p, 5))
    showo("igt_big", ta.gt(p, 4611686018427387904))
    showo("bool_eq", ta.eq(t, u))
    showo("bool_lt", ta.lt(t, u))
    showo("bool_eq_s", ta.eq(t, True))
    i32 = ta.array([2147483647, -2147483648, 0, 1], ta.int32)
    showo("i32", ta.gt(i32, 0))
    try:
        print(ta.eq(i32, 2147483648))
    except OverflowError as exc:
        print("i32 scalar", exc)
    try:
        print(ta.eq(i32, 0.5))
    except TypeError as exc:
        print("int vs float", exc)
    try:
        print(ta.eq(x, p))
    except TypeError as exc:
        print("dtypes", exc)
    try:
        print(ta.lt(t, u[0:3]))
    except ValueError as exc:
        print("shapes", exc)
    # where
    showf("where", ta.where(ta.lt(x, y), x, y))
    showf("where_s", ta.where(ta.lt(x, y), x, 9.5))
    showf("where_sa", ta.where(ta.lt(x, y), 1, y))
    showf("where_nan", ta.where(ta.ne(x, x), nan, x))
    showl("where_i", ta.where(ta.lt(p, q), p, 100))
    showl("where_is", ta.where(ta.lt(p, q), -1, q))
    showo("where_b", ta.where(t, u, False))
    try:
        print(ta.where(t[0:3], x, y))
    except ValueError as exc:
        print("where shapes", exc)
    try:
        print(ta.where(u, p, x))
    except TypeError as exc:
        print("where dtypes", exc)
    try:
        print(ta.where(u, p, 0.5))
    except TypeError as exc:
        print("where float", exc)
    # bytes
    print(ta.frombytes(bytes([0, 1, 2, 255, 0]), ta.bool_))
    showo("frombytes", ta.frombytes(t.tobytes(), ta.bool_))
    print(t == t, t == u, t != u, t == showable(), len(ta.zeros(0, ta.bool_)))
    for v in t:
        print(v, end=" ")
    print(sorted(t), max(t), min(t), sum(t))
    try:
        ta.arange(3, ta.bool_)
    except TypeError as exc:
        print("arange", exc)
    try:
        ta.zeros(True, ta.bool_)
    except TypeError as exc:
        print("zeros", exc)


def showable() -> ta.Array[ta.bool_]:
    return ta.array([True, False, True, False], ta.bool_)


main()
