import math
import ail_array as ta

def show(label: str, a: ta.Array[ta.f32]):
    print(label, a, a.tobytes().hex())


def one(label: str, x: float):
    a = ta.array([x], ta.f32)
    print(label, repr(a[0]), a.tobytes().hex())


def main():
    EDGE = [0.0, -0.0, 1.401298464324817e-45, 1.1754943508222875e-38, 1.1754942106924411e-38,
            3.4028234663852886e+38, 3.4028235677973366e+38, 16777216.0, 16777217.0, 16777219.0,
            1.0000000596046448, 1.0000001788139343, math.inf, -math.inf, math.nan, 0.1, -0.1, 2.5]
    a = ta.array([0.1], ta.f32)
    print(a[0], repr(a))
    show("edge", ta.array(EDGE, ta.f32))
    show("zeros", ta.zeros(5, ta.f32))
    show("empty", ta.zeros(0, ta.f32))
    show("full", ta.full(4, 0.1, ta.f32))
    show("fullbig", ta.full(3, 16777217.0, ta.f32))
    show("fullneg0", ta.full(2, -0.0, ta.f32))
    print(len(a), len(ta.zeros(0, ta.f32)), len(ta.zeros(1, ta.f32)))
    for x in EDGE:
        one("store", x)
    b = ta.array([1.5, -2.5, 3.5, 0.0], ta.f32)
    b[0] = 0.1
    b[1] = 1e300
    b[2] = -0.0
    b[3] = -1e300
    show("set", b)
    b[0] = 16777217.0
    b[1] = 1.401298464324817e-45
    show("set2", b)
    show("negidx", b[-1:])
    show("slice", ta.array(EDGE, ta.f32)[2:9])
    show("slice2", ta.array(EDGE, ta.f32)[::-2])
    c = ta.array([1.0, 2.0, 3.0], ta.f32)
    d = ta.array([7.0, 8.0, 9.0], ta.f32)
    c[0:2] = d[1:3]
    show("setslice", c)
    e = ta.array(EDGE, ta.f32)
    print(e == e, e == ta.array(EDGE, ta.f32), e == ta.zeros(18, ta.f32))
    total = 0.0
    for v in ta.array([0.5, 0.25, 2.0], ta.f32):
        total = total + v
    print(total)
    print(list(ta.array([0.1, 2.5], ta.f32)))


main()
