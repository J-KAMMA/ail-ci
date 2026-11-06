import math
import ail_array as ta


def main():
    xs = [0.0, -0.0, 5e-324, 1e-46, 7.006492321624085e-46, 7.1e-46, 1.401298464324817e-45, 1.1754942106924411e-38,
          1.1754943508222875e-38, 0.1, 1.0 / 3.0, 16777217.0, 16777219.0, 1.0000000596046448, 1.0000001788139343,
          3.4028234663852886e+38, 3.4028235677973362e+38, 3.4028235677973366e+38, 1e39, -1e39, 1e308, math.inf,
          -math.inf, math.nan, -2.5, 2.5, 3.5, -0.5, 0.5, 2147483520.0, 2147483648.0, -2147483648.0, -2147483904.0]
    a = ta.array(xs, ta.f64)
    s = a.astype(ta.f32)
    print(s, s.tobytes().hex())
    back = s.astype(ta.f64)
    print(back, back.tobytes().hex())
    print(back == a, s.astype(ta.f32) == s, s.astype(ta.f32).tobytes() == s.tobytes())
    sat = s.astype(ta.int32, overflow='saturate')
    print(sat)
    near = s.astype(ta.int32, rounding='nearest', overflow='saturate')
    print(near)
    ok = ta.array([0.0, -0.0, 1.5, -1.5, 2.5, -2.5, 16777216.0, 1e-45, -0.9, 2147483520.0, -2147483648.0], ta.f32)
    print(ok.astype(ta.int32), ok.astype(ta.int32, 'nearest'))
    ints = ta.array([0, 1, -1, 16777216, 16777217, 16777219, -16777217, 2147483647, -2147483648, 123456789, 33554435], ta.int32)
    f = ints.astype(ta.f32)
    print(f, f.tobytes().hex())
    print(f.astype(ta.int32, overflow='saturate'))
    for k in range(len(s)):
        print(k, s[k], back[k], math.copysign(1.0, s[k]))
    for bad in [ta.array([math.nan], ta.f32), ta.array([math.inf], ta.f32), ta.array([1.0, 3e9], ta.f32)]:
        try:
            print(bad.astype(ta.int32))
        except ValueError as e:
            print("ValueError", e)
        except OverflowError as e:
            print("OverflowError", e)
    try:
        print(s.astype(ta.int32, overflow='wrap'))
    except ValueError as e:
        print("ValueError", e)
    h = ta.array([0.1, 0.2], ta.f64).astype(ta.f32) + ta.array([0.1, 0.2], ta.f32)
    print(h, h.astype(ta.f64) - ta.array([0.2, 0.4], ta.f64))


main()
