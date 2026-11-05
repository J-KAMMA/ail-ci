import math
import ail_array as ta

def main():
    EDGE = [0.0, -0.0, 1.401298464324817e-45, 1.1754943508222875e-38, 1.1754942106924411e-38,
            3.4028234663852886e+38, 3.4028235677973366e+38, 16777216.0, 16777217.0, 16777219.0,
            1.0000000596046448, 1.0000001788139343, math.inf, -math.inf, math.nan, 0.1, -0.1, 2.5]
    xs = ta.array(EDGE, ta.f32)
    print(xs.tolist())
    print(xs.tobytes().hex())
    print(str(xs))
    print(repr(xs))
    print(ta.zeros(0, ta.f32).tobytes().hex())
    print(ta.zeros(0, ta.f32).tolist(), repr(ta.zeros(0, ta.f32)))
    y = xs.astype(ta.f64)
    print(y.tobytes().hex())
    print(y[0], repr(y[2]), repr(y[14]))
    d = ta.array([0.1, -0.0, 1e300, -1e300, math.inf, -math.inf, math.nan, 16777217.0,
                  1.401298464324817e-45, 1e-46, 3.4028235677973366e+38, 2.5], ta.f64)
    f = d.astype(ta.f32)
    print(f, f.tobytes().hex())
    print(f.tolist())
    print(f.astype(ta.f64).tobytes().hex())
    print(f.astype(ta.f32).tobytes().hex())
    i = ta.array([1, -3, 16777217, -16777217, 0, 2147483647], ta.int32)
    print(i.astype(ta.f32), i.astype(ta.f32).tobytes().hex())
    print(ta.array([1.5, -1.5], ta.f32).astype(ta.f64).tolist())
    print(ta.frombytes(bytes.fromhex('00000000 0000803f 00000080 cdcccc3d'), ta.f32))
    try:
        ta.frombytes(bytes([1, 2, 3]), ta.f32)
    except ValueError as exc:
        print("ValueError", exc)
    print(xs[2:5].tobytes().hex(), xs[2:5].tolist())
    print(len(xs), len(ta.zeros(0, ta.f32)))


main()
