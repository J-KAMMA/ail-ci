import math
import ail_array as ta

def show(label: str, a: ta.Array[ta.f32]):
    print(label, a, a.tobytes().hex())


def main():
    EDGE = [0.0, -0.0, 1.401298464324817e-45, 1.1754943508222875e-38, 1.1754942106924411e-38,
            3.4028234663852886e+38, 3.4028235677973366e+38, 16777216.0, 16777217.0, 16777219.0,
            1.0000000596046448, 1.0000001788139343, math.inf, -math.inf, math.nan, 0.1, -0.1, 2.5]
    xs = ta.array(EDGE, ta.f32)
    ys = ta.array([0.0, 0.0, 1.0, -1.0, 1.0, 3.4028234663852886e+38, 1.0, 16777216.0, 16777217.0,
                   1e6, 1.0, -1.0, math.inf, -math.inf, 1.0, 0.2, 0.3, 0.0], ta.f32)
    show("minimum", ta.minimum(xs, ys))
    show("maximum", ta.maximum(xs, ys))
    show("minimum_s", ta.minimum(xs, 0.0))
    show("maximum_s", ta.maximum(xs, -0.0))
    show("minimum_pi", ta.minimum(xs, 0.1))
    show("maximum_pi", ta.maximum(xs, 16777217.0))
    show("clip", ta.clip(xs, -1.0, 2.0))
    show("clipn", ta.clip(xs, math.nan, 2.0))
    show("clip2", ta.clip(xs, -0.0, 0.0))
    show("zeros", ta.minimum(ta.array([-0.0, 0.0], ta.f32), ta.array([0.0, -0.0], ta.f32)))
    show("zeros2", ta.maximum(ta.array([-0.0, 0.0], ta.f32), ta.array([0.0, -0.0], ta.f32)))
    show("minnan", ta.minimum(ta.array([1.0, math.nan], ta.f32), ta.array([math.nan, 1.0], ta.f32)))
    print(ta.min(xs), ta.max(xs), ta.argmin(xs), ta.argmax(xs))
    print(ta.min(ta.array([-0.0, 0.0, -0.0], ta.f32)), ta.max(ta.array([-0.0, 0.0], ta.f32)))
    print(ta.argmin(ta.array([1.0, math.nan, 0.0], ta.f32)), ta.argmax(ta.array([1.0, 2.0, 2.0], ta.f32)))
    try:
        ta.min(ta.zeros(0, ta.f32))
    except ValueError as exc:
        print("ValueError", exc)


main()
