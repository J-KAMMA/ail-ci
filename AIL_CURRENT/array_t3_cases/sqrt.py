import math
import ail_array as ta

def show(label: str, a: ta.Array[ta.f32]):
    print(label, a, a.tobytes().hex())


def main():
    EDGE = [0.0, -0.0, 1.401298464324817e-45, 1.1754943508222875e-38, 1.1754942106924411e-38,
            3.4028234663852886e+38, 3.4028235677973366e+38, 16777216.0, 16777217.0, 16777219.0,
            1.0000000596046448, 1.0000001788139343, math.inf, -math.inf, math.nan, 0.1, -0.1, 2.5]
    xs = ta.array(EDGE, ta.f32)
    show("sqrt", ta.sqrt(xs))
    show("sqrt2", ta.sqrt(ta.array([2.0, 3.0, 0.25, 1e-45, 1e38, 16777217.0, 4.0, 65536.0], ta.f32)))
    show("exp", ta.exp(ta.array([0.0, -0.0, 1.0, -1.0, 88.0, 88.7, 89.0, -87.0, -104.0, math.inf, -math.inf, math.nan, 1e-30], ta.f32)))
    show("log", ta.log(ta.array([1.0, 2.0, 0.5, 0.0, -0.0, -1.0, 1e-45, 3.4028234663852886e+38, math.inf, math.nan], ta.f32)))
    show("tanh", ta.tanh(ta.array([0.0, -0.0, 1.0, -1.0, 20.0, -20.0, 1e-45, math.inf, -math.inf, math.nan], ta.f32)))
    y = ta.array([1.0, 4.0, 9.0, 16.0], ta.f32)
    show("chain", ta.sqrt(y * y + 1.0))
    z = ta.sqrt(xs)
    print(ta.sum(z))
    print(ta.dot(z, z))
    print(z[0], z[1], z[5], z[12], z[13], z[14])


main()
