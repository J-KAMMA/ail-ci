import ail_array as ta


def showf(label: str, a: ta.Array[ta.f64]):
    print(label, a, a.tobytes().hex())


def showl(label: str, a: ta.Array[ta.int64]):
    print(label, a, a.tobytes().hex())


def showo(label: str, a: ta.Array[ta.bool_]):
    print(label, a, a.tobytes().hex())


def fsum(label: str, a: ta.Array[ta.f64], offs: ta.Array[ta.int64]):
    try:
        showf(label, ta.segment_sum(a, offs))
    except ValueError as exc:
        print(label, "ValueError", exc)


def fext(label: str, a: ta.Array[ta.f64], offs: ta.Array[ta.int64]):
    try:
        showf(label + "_min", ta.segment_min(a, offs))
        showf(label + "_max", ta.segment_max(a, offs))
        showl(label + "_argmin", ta.segment_argmin(a, offs))
        showl(label + "_argmax", ta.segment_argmax(a, offs))
    except ValueError as exc:
        print(label, "ValueError", exc)


def lseg(iv: ta.Array[ta.int64], offs: ta.Array[ta.int64]):
    try:
        showl("l_sum", ta.segment_sum(iv, offs))
    except OverflowError as exc:
        print("l_sum", "OverflowError", exc)
    showl("l_wsum", ta.wrapping_segment_sum(iv, offs))


def main():
    nan = float("nan")
    inf = float("inf")
    hi = 9223372036854775807
    lo = -9223372036854775807 - 1
    v = ta.array([3.0, -1.0, 4.0, 1.0, 5.0, 9.0, 2.0, 6.0, 5.0, 3.0], ta.f64)
    fsum("f1", v, ta.array([0, 3, 3, 7, 10], ta.int64))
    fsum("f2_one", v, ta.array([0], ta.int64))
    fsum("f3_all", v, ta.array([0, 10], ta.int64))
    fsum("f4_empty_first", v, ta.array([0, 0, 0, 10, 10], ta.int64))
    fsum("f5_tail_unused", v, ta.array([2, 5], ta.int64))
    fsum("f6_i32_offs", v, ta.array([0, 5, 10], ta.int32))
    fsum("f7_bad_order", v, ta.array([0, 5, 4], ta.int64))
    fsum("f8_bad_hi", v, ta.array([0, 11], ta.int64))
    fsum("f9_bad_neg", v, ta.array([-1, 4], ta.int64))
    fsum("f10_none", v, ta.zeros(0, ta.int64))
    # the fixed order inside a segment: 17 and 1025 elements with cancelling values
    big = ta.zeros(2200, ta.f64)
    for k in range(2200):
        if k % 3 == 0:
            big[k] = 1e16
        elif k % 3 == 1:
            big[k] = 1.0
        else:
            big[k] = -1e16
    bo = ta.array([0, 17, 18, 1043, 1100, 2200, 2200], ta.int64)
    fsum("f11_order", big, bo)
    one = ta.array([0, 2200], ta.int64)
    print(ta.segment_sum(big, one)[0] == ta.sum(big), ta.segment_sum(v[0:3], ta.array([0, 3], ta.int64))[0] == ta.sum(v[0:3]))
    sp = ta.array([nan, 1.0, inf, -inf, -0.0, -0.0, 0.0, -0.0, 1e308, 1e308], ta.f64)
    fsum("f12_specials", sp, ta.array([0, 2, 4, 6, 8, 10], ta.int64))
    fsum("f13_negzero", sp, ta.array([4, 5, 5, 6, 7, 8], ta.int64))
    # extremes
    fext("e1", v, ta.array([0, 3, 7, 10], ta.int64))
    fext("e2_empty", v, ta.array([0, 3, 3, 10], ta.int64))
    fext("e3_nan", sp, ta.array([0, 2, 4, 6, 10], ta.int64))
    fext("e4_ties", ta.array([2.0, 2.0, 1.0, 1.0, 5.0, 5.0], ta.f64), ta.array([0, 2, 4, 6], ta.int64))
    fext("e5_zero", ta.array([0.0, -0.0, -0.0, 0.0], ta.f64), ta.array([0, 2, 4], ta.int64))
    fext("e6_none", v, ta.array([4], ta.int64))
    # ints: exact, int64 result
    iv = ta.array([3, -1, 4, 1, 5, hi, 2, 6, lo, 3], ta.int64)
    lseg(iv, ta.array([0, 3, 3, 5], ta.int64))
    lseg(iv, ta.array([5, 6, 8, 10], ta.int64))
    lseg(iv, ta.array([5, 7], ta.int64))
    lseg(iv, ta.array([5, 6, 7, 9, 10], ta.int64))
    ov = ta.array([0, 3, 3, 7, 10], ta.int64)
    fext("dummy", v, ov)
    i32 = ta.array([2147483647, 2147483647, -2147483648, 5, 5], ta.int32)
    showl("i_sum", ta.segment_sum(i32, ta.array([0, 2, 3, 5], ta.int64)))
    showl("i_wsum", ta.wrapping_segment_sum(i32, ta.array([0, 2, 3, 5], ta.int64)))
    ev = ta.array([0, 3, 7, 10], ta.int64)
    showl("l_min", ta.segment_min(iv, ev))
    showl("l_max", ta.segment_max(iv, ev))
    showl("l_argmin", ta.segment_argmin(iv, ev))
    showl("l_argmax", ta.segment_argmax(iv, ev))
    try:
        showl("l_empty", ta.segment_max(iv, ov))
    except ValueError as exc:
        print("l_empty", exc)
    bv = ta.array([True, False, True, True, False, False], ta.bool_)
    bo2 = ta.array([0, 2, 2, 6], ta.int64)
    showl("o_sum", ta.segment_sum(bv, bo2))
    showl("o_wsum", ta.wrapping_segment_sum(bv, bo2))
    bo3 = ta.array([0, 2, 4, 6], ta.int64)
    showo("o_min", ta.segment_min(bv, bo3))
    showo("o_max", ta.segment_max(bv, bo3))
    showl("o_argmin", ta.segment_argmin(bv, bo3))
    showl("o_argmax", ta.segment_argmax(bv, bo3))
    try:
        print(ta.segment_sum(v, v))
    except TypeError as exc:
        print("float offsets", exc)
    try:
        print(ta.wrapping_segment_sum(v, ov))
    except TypeError as exc:
        print("wrapping float", exc)


main()
