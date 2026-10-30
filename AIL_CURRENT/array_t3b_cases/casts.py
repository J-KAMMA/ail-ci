import ail_array as ta


def showl(label: str, a: ta.Array[ta.int64]):
    print(label, a, a.tobytes().hex())


def showi(label: str, a: ta.Array[ta.int32]):
    print(label, a, a.tobytes().hex())


def showf(label: str, a: ta.Array[ta.f64]):
    print(label, a, a.tobytes().hex())


def showo(label: str, a: ta.Array[ta.bool_]):
    print(label, a, a.tobytes().hex())


def main():
    hi = 9223372036854775807
    lo = -9223372036854775807 - 1
    nan = float("nan")
    inf = float("inf")
    big = ta.array([0, 1, -1, 255, 256, -129, 65519, 65520, 16777217, 9007199254740993, 4611686018427387905, 4611686293305294849, 2147483647,
                    2147483648, -2147483648, -2147483649, hi, lo, hi - 1000, lo + 1000, 4294967303], ta.int64)
    # int64 -> f64: one rounding (the value of the C cast)
    showf("to_f64", big.astype(ta.f64))
    # int64 -> int32
    try:
        showi("to_i32_raise", big.astype(ta.int32))
    except OverflowError as exc:
        print("to_i32_raise", "OverflowError", exc)
    showi("to_i32_saturate", big.astype(ta.int32, "trunc", "saturate"))
    showi("to_i32_wrap", big.astype(ta.int32, "trunc", "wrap"))
    showi("to_i32_small", big[0:9].astype(ta.int32))
    showl("i32_to_i64", ta.array([-2147483648, 5, 2147483647], ta.int32).astype(ta.int64))
    showl("copy", big.astype(ta.int64))
    # f64 -> int64
    fs = ta.array([0.0, -0.0, 0.5, -0.5, 1.5, -1.5, 2.5, -2.5, 0.9999999, 4294967296.5, 1e18, -1e18, 4503599627370495.5, 9007199254740992.0,
                   9223372036854774784.0, -9223372036854775808.0], ta.f64)
    showl("f_trunc", fs.astype(ta.int64))
    showl("f_nearest", fs.astype(ta.int64, "nearest"))
    for bad in (9223372036854775808.0, -9223372036854777856.0, 1e19, inf, -inf, nan):
        v = ta.array([1.0, bad], ta.f64)
        try:
            showl("f_bad_raise", v.astype(ta.int64))
        except OverflowError as exc:
            print("f_bad_raise", "OverflowError", exc)
        except ValueError as exc:
            print("f_bad_raise", "ValueError", exc)
        showl("f_bad_saturate", v.astype(ta.int64, "trunc", "saturate"))
    try:
        print(fs.astype(ta.int64, "trunc", "wrap"))
    except ValueError as exc:
        print("wrap float", exc)
    try:
        print(fs.astype(ta.int64, "round", "raise"))
    except ValueError as exc:
        print("rounding", exc)
    # to bool: nonzero (NaN is True, -0.0 is False)
    showo("f_to_bool", ta.array([0.0, -0.0, nan, inf, 1e-300, -1.0], ta.f64).astype(ta.bool_))
    showo("l_to_bool", big[0:5].astype(ta.bool_))
    showo("i_to_bool", ta.array([0, 2, -2, 0], ta.int32).astype(ta.bool_))
    showo("o_to_bool", ta.array([True, False], ta.bool_).astype(ta.bool_))
    # from bool
    b = ta.array([True, False, True], ta.bool_)
    showl("o_to_l", b.astype(ta.int64))
    showi("o_to_i", b.astype(ta.int32))
    showf("o_to_f", b.astype(ta.f64))
    # int32 -> f64, f64 -> int32 (unchanged by stage T3b)
    showf("i_to_f", ta.array([2147483647, -2147483648, 0], ta.int32).astype(ta.f64))
    showi("f_to_i", ta.array([1.9, -1.9, 2.5], ta.f64).astype(ta.int32))
    try:
        print(ta.array([3000000000.0], ta.f64).astype(ta.int32))
    except OverflowError as exc:
        print("f_to_i", exc)


main()
