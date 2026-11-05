import math
import ail_array as ta

def show(label: str, a: ta.Array[ta.f32]):
    print(label, a, a.tobytes().hex())


def main():
    EDGE = [0.0, -0.0, 1.401298464324817e-45, 1.1754943508222875e-38, 1.1754942106924411e-38,
            3.4028234663852886e+38, 3.4028235677973366e+38, 16777216.0, 16777217.0, 16777219.0,
            1.0000000596046448, 1.0000001788139343, math.inf, -math.inf, math.nan, 0.1, -0.1, 2.5]
    xs = ta.array(EDGE, ta.f32)
    ys = ta.array([0.0, 0.0, 1.401298464324817e-45, 2.0, -2.0, 1e-30, 3.4028234663852886e+38,
                   16777216.0, 1.0, 2.0, 1.0000001192092896, 1.0, 1.0, 1.0, 1.0, 0.2, 0.3, 0.0], ta.f32)
    show("add", xs + ys)
    show("sub", xs - ys)
    show("mul", xs * ys)
    show("div", xs / ys)
    show("neg", -xs)
    show("abs", abs(xs))
    show("adds", xs + 1.5)
    show("subs", xs - 1)
    show("muls", xs * 2)
    show("divs", xs / 0.0)
    show("divs3", xs / 3)
    show("radd", 1.5 + xs)
    show("rsub", 10 - xs)
    show("rmul", 0.5 * xs)
    show("rdiv", 1.0 / xs)
    show("rdiv0", 0.0 / xs)
    show("divnan", xs / math.nan)
    show("addbig", ta.array([16777217.0], ta.f32) + ta.array([1.0], ta.f32))
    show("mulovf", ta.array([1e30], ta.f32) * ta.array([1e30], ta.f32))
    show("subinf", ta.array([math.inf], ta.f32) - ta.array([math.inf], ta.f32))
    show("absneg0", abs(ta.array([-0.0], ta.f32)))
    show("negzero", -ta.array([0.0], ta.f32))
    print(ta.array([-0.0], ta.f32)[0], ta.array([-0.0], ta.f32).tobytes().hex())
    p = ta.array([math.inf, -math.inf, math.inf], ta.f32)
    q = ta.array([math.inf, math.inf, -math.inf], ta.f32)
    show("infcomb", p + q)
    show("zerodiv", ta.array([1.0, -1.0, 0.0, 1.0], ta.f32) / ta.array([0.0, 0.0, 0.0, -0.0], ta.f32))
    show("scalar0", xs * 0.1)
    show("subint", 3 - xs)
    print(len(xs + ys))


main()
