import math
import ail_array as ta


def fill(x: ta.Matrix[ta.f64], seed: int):
    r, c = x.shape
    s = seed
    for i in range(r):
        for j in range(c):
            s = (s * 1103515245 + 12345) % 2147483648
            x[i, j] = (s % 2001 - 1000) / 8.0


def special(what: int) -> float:
    if what == 0:
        return math.inf
    if what == 1:
        return -math.inf
    if what == 2:
        return math.nan
    if what == 3:
        return -0.0
    if what == 4:
        return 1e308
    if what == 5:
        return -1e308
    if what == 6:
        return 5e-324
    if what == 7:
        return 2.2250738585072014e-308
    if what == 8:
        return 1e-200
    return 0.0


def main():
    ks = [1, 2, 15, 16, 17, 33, 1023, 1024, 1025, 2049]
    for k in ks:
        poss = [0, k // 2, k - 1]
        if k > 17:
            poss = [0, 1, 15, 16, 17, k - 1]
        for pos in poss:
            if pos >= k:
                continue
            for what in range(10):
                a = ta.zeros((2, k), ta.f64)
                b = ta.zeros((k, 2), ta.f64)
                fill(a, 3 + what)
                fill(b, 101 + pos)
                a[1, pos] = special(what)
                b[pos, 0] = special((what + 3) % 10)
                if what == 9:
                    b[pos, 1] = special(4)
                    a[0, pos] = special(4)
                c = ta.matmul(a, b)
                print(k, pos, what, c.tobytes().hex())
    # all zeros, signed zeros, and sums that cancel
    for k in [0, 1, 16, 17, 1025]:
        a = ta.full((1, k), -0.0, ta.f64)
        b = ta.full((k, 1), 0.0, ta.f64)
        print(k, ta.matmul(a, b).tobytes().hex(), ta.matmul(a, ta.full((k, 1), -0.0, ta.f64)).tobytes().hex())
        e = ta.full((1, k), 1e308, ta.f64)
        f = ta.full((k, 1), 10.0, ta.f64)
        print(k, ta.matmul(e, f).tobytes().hex())
        g = ta.full((k, 1), 1e-320, ta.f64)
        h = ta.full((1, k), 1e-10, ta.f64)
        print(k, ta.matmul(h, g).tobytes().hex())


main()
