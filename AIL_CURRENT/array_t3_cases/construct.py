import math
import ail_array as ta


def edges() -> list[float]:
    return [0.0, -0.0, 1.401298464324817e-45, -1.401298464324817e-45, 7.006492321624085e-46, 7.1e-46,
            -7.006492321624085e-46, 1.1754943508222875e-38, 1.1754942106924411e-38, 1.1754943e-38, 16777217.0, 16777219.0,
            -16777217.0, 1.0000000596046448, 1.0000001788139343, 0.1, -2.5, 1.0 / 3.0, 3.4028234663852886e+38,
            3.4028235677973366e+38, 3.4028235677973362e+38, -3.4028235677973366e+38, 1e39, -1e39, math.inf, -math.inf,
            math.nan, 1e300, -1e300, 5e-324, -5e-324, 2.0, 0.5, -1.0, 1e-40, 3.0e-39, 123456789.0, 0.3]


def show(label: str, a: ta.Array[ta.f32]):
    print(label, len(a), a, a.tobytes().hex())


def main():
    xs = edges()
    a = ta.array(xs, ta.f32)
    show("array", a)
    print(a.tolist())
    for k in range(len(a)):
        print(k, repr(xs[k]), a[k], a[-1 - k], math.copysign(1.0, a[k]))
    print(ta.array([0.1], ta.f32)[0])
    show("ints", ta.array([0, 1, -1, 16777216, 16777217, 16777218, 16777219, 2147483647, -2147483648, 123456789,
                           9007199254740993, -9007199254740993, 9223372036854775807], ta.f32))
    show("bools", ta.array([True, False, True], ta.f32))
    show("zeros", ta.zeros(5, ta.f32))
    show("zeros0", ta.zeros(0, ta.f32))
    show("full", ta.full(4, 0.1, ta.f32))
    show("fullint", ta.full(3, 16777217, ta.f32))
    show("fullbig", ta.full(2, 1e39, ta.f32))
    show("fullnan", ta.full(2, -math.nan, ta.f32))
    show("comp", ta.array([k * 0.1 for k in range(12)], ta.f32))
    show("range", ta.array(range(5), ta.f32))
    # stores into an existing array go through the same rounding
    b = ta.zeros(len(xs), ta.f32)
    for k in range(len(xs)):
        b[k] = xs[k]
    show("stored", b)
    print(a == b, a != b)
    c = b.copy()
    c[0] = 7
    c[1] = True
    c[-1] = 0.2
    show("copy", c)
    show("orig", b)
    print(b == c)
    # slices are copies
    show("slice", a[2:9])
    show("slice2", a[::5])
    show("slice3", a[::-7])
    show("slice4", a[30:3:-4])
    d = ta.zeros(10, ta.f32)
    d[2:5] = ta.array([0.1, 0.2, 0.3], ta.f32)
    d[::4] = ta.array([1e39, -0.0, 5e-324], ta.f32)
    show("setslice", d)
    # frombytes / tobytes round trips, canonical NaN
    raw = a.tobytes()
    e = ta.frombytes(raw, ta.f32)
    show("frombytes", e)
    print(e == a)
    f = ta.frombytes(bytes([0, 0, 192, 127, 1, 0, 0, 0, 0, 0, 128, 128, 255, 255, 127, 127, 0, 0, 128, 255]), ta.f32)
    show("fb2", f)
    for k in range(len(f)):
        print(f[k])
    total = 0.0
    for v in a:
        if v == v:
            total = total + v
    print(total, len(list(a)), sorted(ta.array([3.0, -1.5, 0.1], ta.f32)))
    print(str(a[0:3]), repr(a[3:6]), f"{a[6:8]}")


main()
