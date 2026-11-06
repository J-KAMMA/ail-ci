import math
import ail_array as ta


def edges() -> list[float]:
    return [0.0, -0.0, 1.401298464324817e-45, -1.401298464324817e-45, 1.1754943508222875e-38, 1.1754942106924411e-38,
            16777217.0, 16777216.0, 1.0000000596046448, 1.0000001788139343, 0.1, -2.5, 1.0 / 3.0, 3.4028234663852886e+38,
            -3.4028234663852886e+38, 1e39, math.inf, -math.inf, math.nan, 2.0, 0.5, -1.0, 1e-40, 3.0e-39, 123456789.0,
            0.3, 1e-30, 1e30, 7.0, -3.0]


def show(label: str, a: ta.Array[ta.f32]):
    print(label, a, a.tobytes().hex())


def main():
    xs = edges()
    n = len(xs)
    a = ta.array(xs, ta.f32)
    # every pair of the edge set: b is a rotation of a
    for shift in range(0, n, 3):
        ys = [0.0] * n
        for k in range(n):
            ys[k] = xs[(k + shift) % n]
        b = ta.array(ys, ta.f32)
        show("add%d" % shift, a + b)
        show("sub%d" % shift, a - b)
        show("mul%d" % shift, a * b)
        show("div%d" % shift, a / b)
    show("neg", -a)
    show("abs", abs(a))
    show("negneg", -(-a))
    # with Python scalars: the scalar is stored to f32 first
    for s in [0.1, -0.0, 0.0, 1e39, 1e-46, 3.0, 16777217.0, math.inf, math.nan, 1.401298464324817e-45, 1.0000000596046448]:
        show("adds " + repr(s), a + s)
        show("subs " + repr(s), a - s)
        show("rsub " + repr(s), s - a)
        show("muls " + repr(s), a * s)
        show("divs " + repr(s), a / s)
        show("rdiv " + repr(s), s / a)
        show("radd " + repr(s), s + a)
        show("rmul " + repr(s), s * a)
    for i in [0, 1, -1, 3, 16777217, 2147483647]:
        show("addi %d" % i, a + i)
        show("muli %d" % i, a * i)
        show("rdivi %d" % i, i / a)
    show("addb", a + True)
    show("mulb", False * a)
    # chains round after every op
    c = ta.array([0.1, 0.2, 0.3, 1e-45, 3.4e38, 16777216.0], ta.f32)
    show("chain1", c * 3.0 + c)
    show("chain2", (c + c) * (c - 0.1) / 3.0)
    show("chain3", c * c * c * c)
    show("chain4", -c / c - abs(c - 1.0))
    print(ta.array([0.1], ta.f32)[0] + ta.array([0.2], ta.f32)[0], (ta.array([0.1], ta.f32) + ta.array([0.2], ta.f32))[0])
    z = ta.array([0.0, -0.0, 1.0, -1.0, math.inf], ta.f32)
    show("zdiv", z / ta.zeros(5, ta.f32))
    show("zdivn", z / ta.full(5, -0.0, ta.f32))
    show("infs", ta.array([math.inf, math.inf, -math.inf], ta.f32) - ta.array([math.inf, -math.inf, -math.inf], ta.f32))
    show("over", ta.array([3e38, -3e38, 2e38], ta.f32) * 2.0)
    show("under", ta.array([1e-45, 1e-40, -1e-45], ta.f32) * 0.5)
    show("empty", ta.zeros(0, ta.f32) + ta.zeros(0, ta.f32))
    print(c[0] * 3.0 + c[0])


main()
