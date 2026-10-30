import ail_array as ta


def main():
    a = ta.arange(10, ta.int32)
    big = 4611686018427387904
    top = 9223372036854775807
    for lo in (0, 3, -3, big, -big, top, -top):
        for hi in (0, 5, -2, big, -big, top, -top):
            for st in (1, 3, -1, -4, big, -big, top, -top):
                print(lo, hi, st, a[lo:hi:st])
    for i in (big, -big, top, -top, 10, -10, 9, -9):
        try:
            print(i, a[i])
        except IndexError as exc:
            print(i, "IndexError", exc)
    for i in (big, -big, top, -top):
        try:
            a[i] = 1
        except IndexError as exc:
            print(i, "IndexError", exc)
    # int32 products and sums that need 64 bit intermediates
    lo32 = -2147483648
    hi32 = 2147483647
    x = ta.array([lo32, hi32, lo32, hi32], ta.int32)
    y = ta.array([lo32, hi32, hi32, lo32], ta.int32)
    print(ta.wrapping_mul(x, y), ta.saturating_add(x, y), ta.wrapping_sub(x, y), ta.saturating_sub(x, y))
    print(ta.dot(x, y), ta.sum(x), ta.dot(x, x))
    print(ta.dot(ta.array([lo32, lo32], ta.int32), ta.array([lo32, lo32], ta.int32)))
    print(ta.dot(ta.array([lo32] * 4, ta.int32), ta.array([lo32] * 4, ta.int32)))
    try:
        print(x * y)
    except OverflowError as exc:
        print("OverflowError", exc)
    print(x * 1, x // 1, x % 7, x // -7, 7 // ta.array([1, -1, 2, -2], ta.int32), -7 % ta.array([1, -1, 2, -2], ta.int32))
    # lengths around the 16 lane and 1024 block sizes for min/max/argmax too
    for n in (1, 15, 16, 17, 1023, 1024, 1025):
        v = ta.zeros(n, ta.f64)
        for k in range(n):
            v[k] = float((k * 7919) % 1009) - 500.0
        print(n, ta.min(v), ta.max(v), ta.argmin(v), ta.argmax(v), ta.sum(v), ta.dot(v, v))
    # float to int casts near the int32 edges, both rounding modes
    e = ta.array([2147483646.5, 2147483647.0, -2147483647.5, -2147483648.0, 0.49999999999999994, 0.5, 1.5, -0.5, -1.5], ta.f64)
    print(e.astype(ta.int32), e.astype(ta.int32, 'nearest'))
    # f64 <-> bits at the edges
    f = ta.array([5e-324, 2.2250738585072009e-308, 2.2250738585072014e-308, 1.7976931348623157e308, -0.0, 1e-310, 4.9406564584124654e-324], ta.f64)
    print(f.tobytes().hex(), ta.frombytes(f.tobytes(), ta.f64) == f)


main()
