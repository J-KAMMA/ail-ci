import math
import ail_array as ta

SIZES = [0, 1, 15, 16, 17, 1023, 1024, 1025, 5000]


def ramp(n: int) -> ta.Array[ta.f32]:
    a = ta.zeros(n, ta.f32)
    for k in range(n):
        a[k] = 0.1 * (k + 1)
    return a


def alt(n: int) -> ta.Array[ta.f32]:
    a = ta.zeros(n, ta.f32)
    for k in range(n):
        if k % 2 == 0:
            a[k] = 1e8
        else:
            a[k] = -1e8
    return a


def planted(n: int) -> ta.Array[ta.f32]:
    a = ta.zeros(n, ta.f32)
    for k in range(n):
        a[k] = 0.5
    for i in [0, 15, 16, 1023, 1024, 1025]:
        if i < n:
            a[i] = -0.0
    for i in [1, 17, 1022]:
        if i < n:
            a[i] = math.inf
    if n > 2:
        a[2] = -math.inf
    return a


def main():
    for n in SIZES:
        xs = ramp(n)
        ys = alt(n)
        print(n, ta.sum(xs), ta.dot(xs, xs), ta.dot(xs, ys), ta.sum(ys))
    for n in SIZES:
        ps = planted(n)
        print("planted", n, ta.sum(ps), ta.dot(ps, ps))
    for n in [0, 1, 17, 1025]:
        z = ta.zeros(n, ta.f32)
        print("zero", n, ta.sum(z), ta.dot(z, z), repr(ta.sum(z)), repr(ta.dot(z, z)))
    for n in [1, 16, 17, 1024]:
        m = ta.full(n, -0.0, ta.f32)
        print("negzero", n, repr(ta.sum(m)), m.tobytes().hex())
    a = ta.array([0.1, 0.2, 0.3, 0.4, 0.5], ta.f32)
    print(ta.sum(a), ta.sum(a, acc=ta.f64), ta.dot(a, a), ta.dot(a, a, acc=ta.f64))
    b = ta.array([16777217.0, 1.0, -16777217.0, 0.5], ta.f32)
    print(ta.sum(b), ta.dot(b, b), ta.sum(b, acc=ta.f64))
    c = ta.array([math.nan, 1.0, 2.0], ta.f32)
    print(ta.sum(c), ta.dot(c, c), ta.sum(c, acc=ta.f64))
    d = ta.array([math.inf, -math.inf, 1.0], ta.f32)
    print(ta.sum(d), ta.dot(d, d))
    e = ta.array([3.4028234663852886e+38, 3.4028234663852886e+38], ta.f32)
    print(ta.sum(e), ta.dot(e, e))
    print(ta.sum(ta.array([1.401298464324817e-45, 1.401298464324817e-45], ta.f32)))


main()
