import math
import ail_array as ta


def show(label: str, a: ta.Array[ta.f32]):
    print(label, a, a.tobytes().hex())


def main():
    xs = [0.0, -0.0, 1.401298464324817e-45, 1.1754943508222875e-38, 16777217.0, 1.0000000596046448, 0.1, -2.5,
          3.4028234663852886e+38, 1e39, math.inf, -math.inf, math.nan, 0.5, 1e-40, 0.3, 7.0, -1e-30]
    ys = [1.0, 0.0, -0.0, 0.5, 1.0, 3.0, 0.2, 2.5, 2.0, 1.0, math.inf, 1.0, 2.0, math.nan, 1e-40, 3.0, 0.0, 1e30]
    p = ta.array(xs, ta.f32)
    q = ta.array(ys, ta.f32)
    p += q
    show("iadd", p)
    p -= q
    show("isub", p)
    p *= q
    show("imul", p)
    p /= q
    show("idiv", p)
    p += 0.1
    show("iadds", p)
    p -= 1
    show("isubs", p)
    p *= 1e-3
    show("imuls", p)
    p /= 0.0
    show("idivs0", p)
    r = ta.array(xs, ta.f32)
    alias = r
    alias *= 3.0
    show("alias", r)
    print(alias is r, alias == r)
    r += r
    show("self", r)
    r -= r
    show("selfsub", r)
    w = ta.array([1.0] * 40, ta.f32)
    for k in range(30):
        w *= 1.1
        w += 0.01
    show("loop", w)
    acc = ta.zeros(8, ta.f32)
    step = ta.array([0.1, 0.2, 0.3, 0.4, 1e-8, 1e8, -0.1, 3.0], ta.f32)
    for k in range(1000):
        acc += step
    show("accum", acc)
    t = ta.array([1e-45, 1e-45, -1e-45], ta.f32)
    t /= 2.0
    show("half", t)
    t *= -1.0
    show("negz", t)
    u = ta.array([3e38, 1e-45], ta.f32)
    u *= 10
    show("big", u)
    e = ta.zeros(0, ta.f32)
    e += e
    show("empty", e)


main()
