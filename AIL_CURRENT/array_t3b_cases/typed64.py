import ail_array as ta


def showl(label: str, a: ta.Array[ta.int64]):
    print(label, a, a.tobytes().hex())


def showo(label: str, a: ta.Array[ta.bool_]):
    print(label, a, a.tobytes().hex())


def attempt(label: str, a: ta.Array[ta.int64], b: ta.Array[ta.int64], op: int):
    try:
        if op == 0:
            showl(label, a + b)
        elif op == 1:
            showl(label, a - b)
        elif op == 2:
            showl(label, a * b)
        elif op == 3:
            showl(label, a // b)
        else:
            showl(label, a % b)
    except OverflowError as exc:
        print(label, "OverflowError", exc)
    except ZeroDivisionError as exc:
        print(label, "ZeroDivisionError", exc)


def main():
    lo = -9223372036854775807 - 1
    hi = 9223372036854775807
    a = ta.array([0, 1, -1, 7, -7, hi, lo, hi - 1, lo + 1, 4294967296, -4294967296, 3037000499, 3037000500, 4611686018427387904], ta.int64)
    b = ta.array([3, -3, 3, -2, 2, 1, 1, 1, -1, 4294967296, 2147483648, 3037000499, 3037000500, 2], ta.int64)
    for op in range(5):
        attempt("op%d" % op, a, b, op)
    small = a[0:5]
    smallb = b[0:5]
    for op in range(5):
        attempt("small%d" % op, small, smallb, op)
    showl("wadd", ta.wrapping_add(a, b))
    showl("wsub", ta.wrapping_sub(a, b))
    showl("wmul", ta.wrapping_mul(a, b))
    showl("sadd", ta.saturating_add(a, b))
    showl("wneg", ta.wrapping_neg(a))
    showl("wabs", ta.wrapping_abs(a))
    showl("wfloordiv", ta.wrapping_floordiv(a, -1))
    showl("minimum", ta.minimum(a, b))
    showl("clip", ta.clip(a, -10, 10))
    print(ta.min(a), ta.max(a), ta.argmin(a), ta.argmax(a), ta.wrapping_sum(a), ta.wrapping_dot(a, b))
    print(ta.sum(small), ta.sum(smallb))
    e = ta.array([1, 2, hi, 4, 5], ta.int64)
    try:
        e += 1
    except OverflowError as exc:
        print("iadd", exc)
    showl("e", e)
    # comparisons, where, bool logic
    lt = ta.lt(a, b)
    showo("lt", lt)
    showo("eq_s", ta.eq(a, 1))
    showo("ge", ta.ge(a, b))
    showl("where", ta.where(lt, a, b))
    showl("where_s", ta.where(lt, a, 7))
    showo("and", ta.logical_and(lt, ta.ge(a, 0)))
    showo("not", ta.logical_not(lt))
    print(ta.sum(lt), ta.any(lt), ta.all(lt))
    # take / put / strided
    idx = ta.array([13, 0, -1, 5], ta.int64)
    showl("take", ta.take(a, idx))
    c = ta.zeros(5, ta.int64)
    ta.put(c, ta.array([0, 2, 2, -1], ta.int64), ta.array([1, 2, 3, 4], ta.int64))
    showl("put", c)
    ta.put(c, ta.array([0, 0], ta.int64), ta.array([hi, 1], ta.int64), accumulate=True, overflow="wrap")
    showl("put_acc_wrap", c)
    showl("gather", ta.gather_strided(a, 1, [2, 3], [5, 2]))
    d = ta.zeros(8, ta.int64)
    ta.scatter_strided(d, 7, [2, 2], [-4, -1], ta.array([5, 6, 7, 8], ta.int64))
    showl("scatter", d)
    # segments
    offs = ta.array([0, 4, 4, 9, 14], ta.int64)
    showl("segsum", ta.wrapping_segment_sum(a, offs))
    showl("segargmax", ta.segment_argmax(a, ta.array([0, 4, 9, 14], ta.int64)))
    showl("segmax", ta.segment_max(a, ta.array([0, 4, 9, 14], ta.int64)))
    showl("segsum_small", ta.segment_sum(small, ta.array([0, 2, 5], ta.int64)))
    # casts
    print(a.astype(ta.f64))
    print(a.astype(ta.bool_))
    print(a[0:5].astype(ta.int32))


main()
