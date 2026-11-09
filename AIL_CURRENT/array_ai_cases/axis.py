# Reductions along an axis (job aicore1): sum / min / max (keepdims) / argmin / argmax of 2-D f64 and f32 arrays, axis 0, 1,
# -1, -2, row lengths at the lane and block boundaries, specials planted, the empty-row error.
import math
import ail_array as ta


def mf(r: int, c: int, s: int) -> ta.Matrix[ta.f64]:
    m = ta.zeros((r, c), ta.f64)
    for i in range(r):
        for j in range(c):
            s = (1103515245 * s + 12345) % 2147483648
            m[i, j] = float(s % 200001 - 100000) / 3.0
    return m


def ms(r: int, c: int, s: int) -> ta.Matrix[ta.f32]:
    m = ta.zeros((r, c), ta.f32)
    for i in range(r):
        for j in range(c):
            s = (1103515245 * s + 12345) % 2147483648
            m[i, j] = float(s % 200001 - 100000) / 3.0
    return m


def main():
    for c in [1, 15, 16, 17, 1023, 1024, 1025, 2049]:
        a = mf(3, c, c)
        x = ms(3, c, c + 1)
        s1 = ta.sum(a, axis=1)
        t1 = ta.sum(x, axis=1)
        print(c, "f64 sum1", s1, "f32 sum1", t1.tobytes().hex())
        print(c, "rows", ta.sum(a[1]) == s1[1], ta.sum(x[2]) == t1[2])
        print(c, "f64 sum0", ta.sum(ta.sum(a, axis=0)), "f32 sum0", ta.sum(ta.sum(x, axis=0)))
        print(c, "max", ta.max(a, axis=1), ta.max(x, axis=-1), "min", ta.min(a, axis=-1), ta.min(x, axis=1))
        print(c, "arg", ta.argmax(a, axis=1), ta.argmin(x, axis=1))
    a = mf(4, 5, 9)
    a[1, 2] = math.nan
    a[2, 0] = math.inf
    a[3, 4] = -0.0
    a[0, 1] = -math.inf
    x = ms(4, 5, 10)
    x[0, 3] = math.nan
    x[2, 2] = -math.inf
    print("f64 axis0", ta.sum(a, axis=0), ta.max(a, axis=0), ta.min(a, axis=-2), ta.argmax(a, axis=0), ta.argmin(a, axis=0))
    print("f64 keep", ta.sum(a, axis=1, keepdims=True), ta.max(a, axis=0, keepdims=True), ta.min(a, axis=1, keepdims=False))
    print("f32 axis0", ta.sum(x, axis=0), ta.max(x, axis=0), ta.argmax(x, axis=-2))
    print("f32 keep", ta.sum(x, axis=1, keepdims=True), ta.min(x, axis=0, keepdims=True))
    k = ta.max(x, axis=1, keepdims=True)
    r, c = k.shape
    print("shape", r, c, len(ta.sum(x, axis=1)))
    z = ta.zeros((0, 3), ta.f64)
    print("empty", ta.sum(z, axis=1), ta.sum(z, axis=0), ta.max(z, axis=1))
    zs = ta.zeros((2, 0), ta.f32)
    print("empty32", ta.sum(zs, axis=1), ta.sum(zs, axis=0))
    try:
        print(ta.max(zs, axis=1))
    except ValueError as e:
        print("ValueError", e)
    try:
        print(ta.argmin(ta.zeros((2, 0), ta.f64), axis=1))
    except ValueError as e:
        print("ValueError", e)


main()
