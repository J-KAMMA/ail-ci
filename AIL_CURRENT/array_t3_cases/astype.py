import math
import ail_array as ta

def show(label: str, a: ta.Array[ta.f32]):
    print(label, a, a.tobytes().hex())


def main():
    EDGE = [0.0, -0.0, 1.401298464324817e-45, 1.1754943508222875e-38, 1.1754942106924411e-38,
            3.4028234663852886e+38, 3.4028235677973366e+38, 16777216.0, 16777217.0, 16777219.0,
            1.0000000596046448, 1.0000001788139343, math.inf, -math.inf, math.nan, 0.1, -0.1, 2.5]
    xs = ta.array(EDGE, ta.f32)
    print("f64", xs.astype(ta.f64).tobytes().hex())
    print("f32", xs.astype(ta.f32).tobytes().hex())
    wide = xs.astype(ta.f64)
    show("back", wide.astype(ta.f32))
    print(wide.tolist())
    # every f32 value survives f32 -> f64 -> f32 unchanged
    exact = ta.array([16777216.0, 16777217.0, 1e38, 1e-38, 1.401298464324817e-45, -0.0, math.inf], ta.f64)
    show("narrow", exact.astype(ta.f32))
    show("narrow2", exact.astype(ta.f32).astype(ta.f64).astype(ta.f32))
    print(exact.astype(ta.f32).astype(ta.f64).tolist())
    # overflow and half-way to overflow, ties to even through the cast
    tie = ta.array([1.0000000596046448, 1.0000001788139343, 16777217.0, 16777219.0], ta.f64)
    show("tie", tie.astype(ta.f32))
    huge = ta.array([3.4028234663852886e+38, 3.4028235677973366e+38, 3.402823669209385e+38, 1e300, -1e300], ta.f64)
    show("huge", huge.astype(ta.f32))
    tiny = ta.array([1e-46, 7.0e-46, 1.401298464324817e-45, 2.802596928649634e-45], ta.f64)
    show("tiny", tiny.astype(ta.f32))
    nan = ta.array([math.nan, -math.nan], ta.f64)
    show("nan", nan.astype(ta.f32))
    ints = ta.array([0, 1, -1, 16777216, 16777217, -16777217, 2147483647, -2147483648], ta.int32)
    show("ints", ints.astype(ta.f32))
    print(ints.astype(ta.f32).astype(ta.f64).tolist())
    vals = ta.array([0.0, -0.0, 0.5, 1.5, -2.5, 16777216.0, -16777216.0, 2.0], ta.f32)
    print(vals.astype(ta.int32))
    print(vals.astype(ta.int32, "nearest"))
    print(vals.astype(ta.int32, "nearest", "saturate"))
    big = ta.array([1e38, -1e38, 2147483648.0, -2147483648.0], ta.f32)
    try:
        print(big.astype(ta.int32))
    except OverflowError as exc:
        print("OverflowError", exc)
    print(big.astype(ta.int32, "trunc", "saturate"))
    print(big.astype(ta.int32, "nearest", "saturate"))
    for k in range(len(vals)):
        one = vals[k]
        print(k, repr(one))
    try:
        ta.array([math.nan], ta.f32).astype(ta.f64).astype(ta.int32)
    except ValueError as exc:
        print("ValueError", exc)
    try:
        ta.array([math.inf], ta.f32).astype(ta.f64).astype(ta.int32)
    except OverflowError as exc:
        print("OverflowError", exc)


main()
