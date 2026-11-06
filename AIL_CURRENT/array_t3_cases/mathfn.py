import math
import ail_array as ta


def show(label: str, a: ta.Array[ta.f32]):
    print(label, a, a.tobytes().hex())


def main():
    xs = [0.0, -0.0, 1.401298464324817e-45, 1.1754943508222875e-38, 2.0, 3.0, 4.0, 0.1, 16777217.0, -1.0, -1e-45,
          3.4028234663852886e+38, math.inf, -math.inf, math.nan, 0.5, 1e-40, 88.0, 88.7228, 89.0, -103.0, -104.0, 1e30,
          123456.789, 0.75, 1e-10]
    a = ta.array(xs, ta.f32)
    show("sqrt", ta.sqrt(a))
    show("exp", ta.exp(a))
    show("log", ta.log(a))
    show("tanh", ta.tanh(a))
    show("sqrtsq", ta.sqrt(a * a))
    ys = [1.0, 0.0, 0.0, -0.0, math.nan, 3.0, -4.0, 0.2, 16777216.0, -1.0, 1e-45, math.inf, 1.0, 0.0, 1.0, math.nan,
          -1e-40, 88.0, -88.0, 90.0, -103.0, 0.0, 1e31, 1.0, 0.75, -1e-10]
    b = ta.array(ys, ta.f32)
    show("minimum", ta.minimum(a, b))
    show("maximum", ta.maximum(a, b))
    show("minimum_r", ta.minimum(b, a))
    show("maximum_r", ta.maximum(b, a))
    show("mins int", ta.minimum(a, 3))
    show("maxs int", ta.maximum(a, -2))
    for s in [0.0, -0.0, 0.1, 1e39, math.nan, -1.0, 3.0]:
        show("mins " + repr(s), ta.minimum(a, s))
        show("maxs " + repr(s), ta.maximum(a, s))
    show("clip", ta.clip(a, -1.0, 2.0))
    show("clip0", ta.clip(a, -0.0, 0.0))
    show("clipn", ta.clip(a, math.nan, 2.0))
    show("clipb", ta.clip(a, 0.1, 0.30000001))
    z = ta.array([0.0, -0.0], ta.f32)
    w = ta.array([-0.0, 0.0], ta.f32)
    show("mz", ta.minimum(z, w))
    show("xz", ta.maximum(z, w))
    print(ta.min(a), ta.max(a), ta.argmin(a), ta.argmax(a))
    c = ta.array([3.0, -0.0, 0.0, -0.0, 1e-45, -1e-45, 7.0, 7.0], ta.f32)
    print(ta.min(c), ta.max(c), ta.argmin(c), ta.argmax(c))
    d = ta.array([0.0, -0.0, 0.0], ta.f32)
    print(ta.min(d), ta.max(d), ta.argmin(d), ta.argmax(d))
    e = ta.array([1.0, 2.0, math.nan, -5.0, math.nan], ta.f32)
    print(ta.min(e), ta.max(e), ta.argmin(e), ta.argmax(e))
    f = ta.array([0.1, 0.10000000149011612, 0.1000000001], ta.f32)
    print(ta.min(f), ta.max(f), ta.argmin(f), ta.argmax(f), f)


main()
