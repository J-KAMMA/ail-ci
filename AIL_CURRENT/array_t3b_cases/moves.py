import ail_array as ta


def showf(label: str, a: ta.Array[ta.f64]):
    print(label, a, a.tobytes().hex())


def showi(label: str, a: ta.Array[ta.int32]):
    print(label, a, a.tobytes().hex())


def showl(label: str, a: ta.Array[ta.int64]):
    print(label, a, a.tobytes().hex())


def showo(label: str, a: ta.Array[ta.bool_]):
    print(label, a, a.tobytes().hex())


def take_f(label: str, a: ta.Array[ta.f64], idx: ta.Array[ta.int64]):
    try:
        showf(label, ta.take(a, idx))
    except IndexError as exc:
        print(label, "IndexError", exc)


def take_i(label: str, a: ta.Array[ta.int32], idx: ta.Array[ta.int32]):
    try:
        showi(label, ta.take(a, idx))
    except IndexError as exc:
        print(label, "IndexError", exc)


def gather_f(label: str, a: ta.Array[ta.f64], off: int, shape: list[int], strides: list[int]):
    try:
        showf(label, ta.gather_strided(a, off, shape, strides))
    except IndexError as exc:
        print(label, "IndexError", exc)
    except ValueError as exc:
        print(label, "ValueError", exc)


def scatter_f(label: str, a: ta.Array[ta.f64], off: int, shape: list[int], strides: list[int], src: ta.Array[ta.f64]):
    try:
        ta.scatter_strided(a, off, shape, strides, src)
    except IndexError as exc:
        print(label, "IndexError", exc)
    except ValueError as exc:
        print(label, "ValueError", exc)
    showf(label, a)


def main():
    nan = float("nan")
    inf = float("inf")
    hi = 9223372036854775807
    lo = -9223372036854775807 - 1
    x = ta.array([10.0, -0.0, nan, inf, -inf, 0.1, 5e-324, 1.7976931348623157e308], ta.f64)
    take_f("take", x, ta.array([0, 2, -1, 1, 7, -8, 2], ta.int64))
    take_f("take_empty", x, ta.zeros(0, ta.int64))
    take_f("take_oob", x, ta.array([0, 8], ta.int64))
    take_f("take_oob_neg", x, ta.array([-9], ta.int64))
    take_f("take_huge", x, ta.array([hi, 0], ta.int64))
    take_f("take_lo", x, ta.array([lo], ta.int64))
    take_f("take_i32", x, ta.array([1, 2], ta.int64))
    take_i("take_i", ta.array([5, -6, 7], ta.int32), ta.array([2, 2, -3, 0], ta.int32))
    take_i("take_i_oob", ta.array([5, -6, 7], ta.int32), ta.array([3], ta.int32))
    try:
        print(ta.take(x, x))
    except TypeError as exc:
        print("take float idx", exc)
    bidx = ta.array([True, False], ta.bool_)
    try:
        print(ta.take(x, bidx))
    except TypeError as exc:
        print("take bool idx", exc)
    showl("take_l", ta.take(ta.array([hi, lo, 0, 1], ta.int64), ta.array([1, 0, 0, -1], ta.int64)))
    showo("take_o", ta.take(ta.array([True, False, True], ta.bool_), ta.array([2, 1, 0, 0], ta.int64)))
    # put
    y = ta.zeros(5, ta.f64)
    ta.put(y, ta.array([0, 2], ta.int64), ta.array([1.5, -2.5], ta.f64))
    showf("put", y)
    ta.put(y, ta.array([1, 1, 1], ta.int64), ta.array([1.0, 2.0, 3.0], ta.f64))
    showf("put_dup", y)
    ta.put(y, ta.array([-1, -5], ta.int64), 7)
    showf("put_scalar", y)
    ta.put(y, ta.array([0, 0, 4], ta.int64), ta.array([1.0, 2.0, 0.5], ta.f64), accumulate=True)
    showf("put_acc", y)
    ta.put(y, ta.array([3], ta.int64), nan, accumulate=True)
    showf("put_acc_nan", y)
    try:
        ta.put(y, ta.array([0, 5], ta.int64), ta.array([9.0, 9.0], ta.f64))
    except IndexError as exc:
        print("put_oob", exc)
    showf("put_oob_after", y)
    try:
        ta.put(y, ta.array([0, 1], ta.int64), ta.array([9.0], ta.f64))
    except ValueError as exc:
        print("put_len", exc)
    z = ta.array([hi - 2, 5, lo], ta.int64)
    ta.put(z, ta.array([0, 0], ta.int64), ta.array([1, 1], ta.int64), accumulate=True)
    showl("put_acc_l", z)
    try:
        ta.put(z, ta.array([0, 0, 1], ta.int64), ta.array([1, 1, 1], ta.int64), accumulate=True)
    except OverflowError as exc:
        print("put_acc_over", exc)
    showl("put_acc_over_after", z)
    ta.put(z, ta.array([0, 0, 2], ta.int64), ta.array([hi, 5, -1], ta.int64), accumulate=True, overflow="wrap")
    showl("put_acc_wrap", z)
    w = ta.array([2147483647, 1], ta.int32)
    try:
        ta.put(w, ta.array([0], ta.int32), 1, accumulate=True)
    except OverflowError as exc:
        print("put_acc_i32", exc)
    ta.put(w, ta.array([0], ta.int32), 1, accumulate=True, overflow="wrap")
    showi("put_acc_i32_wrap", w)
    bo = ta.zeros(4, ta.bool_)
    ta.put(bo, ta.array([1, 3], ta.int64), True)
    showo("put_o", bo)
    ta.put(bo, ta.array([0, 1], ta.int64), ta.array([True, False], ta.bool_))
    showo("put_o2", bo)
    # strided gather
    base = ta.array([float(k) * 1.5 - 4.0 for k in range(24)], ta.f64)
    gather_f("g1", base, 0, [24], [1])
    gather_f("g2", base, 1, [2, 2], [1, 4])
    gather_f("g3", base, 0, [3, 4], [4, 1])
    gather_f("g4_transpose", base, 0, [4, 3], [1, 4])
    gather_f("g5_broadcast", base, 3, [2, 3], [0, 2])
    gather_f("g6_3d", base, 2, [2, 3, 2], [12, 3, 1])
    gather_f("g7_empty", base, 7, [0, 3], [1, 1])
    gather_f("g8_rank0", base, 7, [], [])
    gather_f("g9_last", base, 23, [1], [100])
    gather_f("g10_reverse", base, 23, [6], [-4])
    gather_f("g11_neg_2d", base, 22, [2, 3], [-12, -3])
    gather_f("g12_oob_hi", base, 20, [3, 3], [1, 1])
    gather_f("g13_oob_lo", base, 2, [4], [-1])
    gather_f("g14_oob_off", base, 24, [1], [1])
    gather_f("g15_oob_negoff", base, -1, [1], [1])
    gather_f("g16_len", base, 0, [2, 2], [1])
    gather_f("g17_neg", base, 0, [2, -1], [1, 1])
    gather_f("g18_zero_stride", base, 5, [4], [0])
    gather_f("g19_specials", x, 0, [2, 4], [4, 1])
    showl("g_l", ta.gather_strided(ta.array([hi, lo, 0, 1, 2, 3], ta.int64), 5, [3, 2], [-2, -1]))
    showi("g_i", ta.gather_strided(ta.array([hi, lo, 0, 1, 2, 3], ta.int64).astype(ta.int32, "trunc", "wrap"), 0, [2, 3], [3, 1]))
    showo("g_o", ta.gather_strided(ta.array([True, False, False, True], ta.bool_), 0, [2, 2], [1, 2]))
    # strided scatter
    s = ta.zeros(24, ta.f64)
    scatter_f("s1", s, 1, [2, 2], [1, 4], ta.array([1.0, 2.0, 3.0, 4.0], ta.f64))
    scatter_f("s2", s, 3, [2, 3], [6, 2], ta.array([5.0, 6.0, 7.0, 8.0, 9.0, 10.0], ta.f64))
    scatter_f("s3_overlap", s, 0, [3], [0], ta.array([-1.0, -2.0, -3.0], ta.f64))
    scatter_f("s4_oob", s, 22, [3], [1], ta.array([1.0, 1.0, 1.0], ta.f64))
    scatter_f("s5_len", s, 0, [3], [1], ta.array([1.0, 1.0], ta.f64))
    scatter_f("s6_specials", s, 8, [2, 2], [1, 3], ta.array([nan, -0.0, inf, -inf], ta.f64))
    ta.scatter_strided(s, 16, [2, 2], [4, 1], 0.5)
    showf("s7_scalar", s)
    ta.scatter_strided(s, 0, [0], [1], 9.0)
    ta.scatter_strided(s, 5, [], [], 11)
    showf("s8_rank0", s)
    t = ta.zeros(6, ta.int64)
    ta.scatter_strided(t, 5, [3], [-2], ta.array([hi, lo, 7], ta.int64))
    showl("s_l", t)
    to = ta.zeros(4, ta.bool_)
    ta.scatter_strided(to, 0, [2], [3], True)
    showo("s_o", to)
    # round trip: gather then scatter back through the same view
    v = ta.array([float(k) for k in range(12)], ta.f64)
    g = ta.gather_strided(v, 1, [3, 3], [4, 1])
    u = ta.zeros(12, ta.f64)
    ta.scatter_strided(u, 1, [3, 3], [4, 1], g)
    showf("roundtrip", u)


main()
