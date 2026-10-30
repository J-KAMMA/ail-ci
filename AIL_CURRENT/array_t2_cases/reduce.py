import math
import ail_array as ta


def bits(x: float) -> str:
    return ta.array([x], ta.f64).tobytes().hex()


def make(kind: int, n: int) -> ta.Array[ta.f64]:
    a = ta.zeros(n, ta.f64)
    seed = 12345 + kind * 7919
    for k in range(n):
        seed = (seed * 1103515245 + 12345) % 2147483648
        if kind == 0:
            a[k] = 0.1 * k
        elif kind == 1:
            if k % 3 == 0:
                a[k] = 1e16
            elif k % 3 == 1:
                a[k] = 1.0
            else:
                a[k] = -1e16
        elif kind == 2:
            a[k] = (seed % 2001 - 1000) / 7.0
        elif kind == 3:
            a[k] = 1.0 / (k + 1)
        elif kind == 4:
            a[k] = -0.0
        elif kind == 5:
            a[k] = 1e308 if k % 2 == 0 else -1e308
        else:
            a[k] = (seed % 1000003) * 1e-300
    return a


def line(label: str, n: int, a: ta.Array[ta.f64], b: ta.Array[ta.f64]):
    s = ta.sum(a)
    d = ta.dot(a, b)
    print(label, n, bits(s), bits(d), bits(sum(a)), s, d)


def main():
    lengths = [0, 1, 2, 3, 15, 16, 17, 31, 32, 33, 1023, 1024, 1025, 1536, 2047, 2048, 2049, 3071, 3072, 3073, 4097, 5000]
    for kind in range(7):
        for n in lengths:
            a = make(kind, n)
            b = make((kind + 3) % 7, n)
            line("kind%d" % kind, n, a, b)
    # specials at lane and block boundaries
    for pos in [0, 1, 15, 16, 17, 1023, 1024, 1025, 2047, 2048, 2049]:
        n = 2100
        for what in range(5):
            a = ta.zeros(n, ta.f64)
            for k in range(n):
                a[k] = 1.0 + 0.001 * (k % 17)
            if what == 0:
                a[pos] = math.inf
            elif what == 1:
                a[pos] = math.nan
            elif what == 2:
                a[pos] = -math.inf
                a[n - 1 - pos] = math.inf
            elif what == 3:
                a[pos] = -0.0
            else:
                a[pos] = 1e308
                a[(pos + 5) % n] = 1e308
            b = a.copy()
            line("pos%d_%d" % (pos, what), n, a, b)
    # -0.0 / 0.0 mixes
    z = ta.array([-0.0, 0.0], ta.f64)
    print(bits(ta.sum(z)), bits(ta.sum(z[::-1])), bits(ta.sum(ta.full(17, -0.0, ta.f64))), bits(ta.sum(ta.zeros(17, ta.f64))))
    # extremes over larger arrays
    big = make(2, 5000)
    print(ta.min(big), ta.max(big), ta.argmin(big), ta.argmax(big))
    ints = ta.arange(5000, ta.int32)
    print(ta.sum(ints), ta.min(ints), ta.max(ints), ta.argmin(ints), ta.argmax(ints), ta.dot(ints, ints))
    # int32 reductions near the int32 / int64 limits
    h = ta.full(3000, 2147483647, ta.int32)
    print(ta.sum(h), ta.dot(h, h))
    l = ta.full(3000, -2147483648, ta.int32)
    print(ta.sum(l), ta.dot(l, l), ta.dot(h, l))


main()
