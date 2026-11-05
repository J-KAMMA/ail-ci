import math
import ail_array as ta

def show(label: str, a: ta.Array[ta.f32]):
    print(label, a, a.tobytes().hex())


def main():
    EDGE = [0.0, -0.0, 1.401298464324817e-45, 1.1754943508222875e-38, 1.1754942106924411e-38,
            3.4028234663852886e+38, 3.4028235677973366e+38, 16777216.0, 16777217.0, 16777219.0,
            1.0000000596046448, 1.0000001788139343, math.inf, -math.inf, math.nan, 0.1, -0.1, 2.5]
    xs = ta.array(EDGE, ta.f32)
    ys = ta.array([0.0, 0.0, 1.0, 0.5, -0.5, 1e10, 1e10, 1.0, 1.0, -1.0, 0.5, 1.0, 1.0, 1.0, 1.0, 0.2, 0.3, 0.0], ta.f32)
    p = xs.copy()
    p += ys
    show("iadd", p)
    p -= ys
    show("isub", p)
    p *= ys
    show("imul", p)
    p /= ys
    show("idiv", p)
    q = p
    q += 1.0
    show("alias", p)
    print(p is q)
    r = ta.array([0.1, 2.5, -0.0], ta.f32)
    r += 0.1
    show("iadd_s", r)
    r *= 16777217.0
    show("imul_s", r)
    r -= 1e300
    show("isub_s", r)
    r /= 3.0
    show("idiv_s", r)
    t = ta.array([1.0, 2.0, 4.0], ta.f32)
    t *= t
    show("selfmul", t)
    t /= t
    show("selfdiv", t)
    u = ta.zeros(3, ta.f32)
    u += ta.array([-0.0, 0.0, -0.0], ta.f32)
    show("izero", u)
    v = ta.array([math.inf, 1.0, math.nan], ta.f32)
    v -= ta.array([math.inf, math.inf, 1.0], ta.f32)
    show("iinf", v)
    w = ta.array([16777216.0, 16777217.0], ta.f32)
    w += 1.0
    show("iround", w)
    w /= 1e30
    show("itiny", w)


main()
