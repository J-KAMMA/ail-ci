import math
import ail_array as ta


def bits(x: float) -> str:
    return ta.array([x], ta.f64).tobytes().hex()


def make(kind: int, n: int) -> ta.Array[ta.f64]:
    a = ta.zeros(n, ta.f64)
    seed = 12345 + (kind % 16) * 7919
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
        elif kind == 6:
            a[k] = (seed % 1000003) * 1e-300
        elif kind == 7:
            a[k] = 1.0 + (seed % 17) * 1e-16
        else:
            a[k] = (seed % 2001 - 1000) * 3.5
    return a


def line(label: str, n: int, a: ta.Array[ta.f64], b: ta.Array[ta.f64]):
    s = ta.sum(a)
    d = ta.dot(a, b)
    print(label, n, bits(s), bits(d), s, d)


def main():
    lengths = [0, 1, 2, 15, 16, 17, 31, 32, 33, 1023, 1024, 1025, 1536, 2047, 2048, 2049, 3071, 3072, 3073, 4097, 5000, 20000, 100003]
    for kind in range(9):
        for n in lengths:
            a = make(kind, n)
            b = make((kind + 3) % 9, n)
            line("kind%d" % kind, n, a, b)
    # specials planted at lane and block boundaries (two whole blocks and a short third one)
    for pos in [0, 1, 15, 16, 17, 1023, 1024, 1025, 2047, 2048, 2049]:
        n = 2100
        for what in range(7):
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
            elif what == 4:
                a[pos] = 1e308
                a[(pos + 5) % n] = 1e308
            elif what == 5:
                a[pos] = 1e-310
            else:
                a[pos] = -1e308
                a[(pos + 16) % n] = 1e308
            b = a.copy()
            line("pos%d_%d" % (pos, what), n, a, b)
    # all -0.0 and mixes of zeros, whole blocks and a short one
    for n in [1, 16, 1024, 1040, 2048, 2049]:
        z = ta.full(n, -0.0, ta.f64)
        p = ta.zeros(n, ta.f64)
        line("negzero", n, z, p)
        line("zero", n, p, z)
        line("negneg", n, z, z)
    # a larger array with a NaN near the end, and one with infinities that cancel in the tree
    big = make(2, 70000)
    big[69999] = math.nan
    line("bignan", 70000, big, big)
    big2 = make(2, 70000)
    big2[1] = math.inf
    big2[1030] = -math.inf
    line("bigcancel", 70000, big2, make(8, 70000))


main()
