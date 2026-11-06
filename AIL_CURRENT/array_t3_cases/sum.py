import math
import ail_array as ta


def bits(x: float) -> str:
    return ta.array([x], ta.f64).tobytes().hex()


def make(kind: int, n: int) -> ta.Array[ta.f32]:
    a = ta.zeros(n, ta.f32)
    seed = 4242 + kind * 7919
    for k in range(n):
        seed = (seed * 1103515245 + 12345) % 2147483648
        if kind == 0:
            a[k] = 0.1 * k
        elif kind == 1:
            if k % 3 == 0:
                a[k] = 1e8
            elif k % 3 == 1:
                a[k] = 1.0
            else:
                a[k] = -1e8
        elif kind == 2:
            a[k] = (seed % 2001 - 1000) / 7.0
        elif kind == 3:
            a[k] = 1.0 / (k + 1)
        elif kind == 4:
            a[k] = -0.0
        elif kind == 5:
            a[k] = 3e38 if k % 2 == 0 else -3e38
        elif kind == 6:
            a[k] = (seed % 1000003) * 1e-45
        else:
            a[k] = 16777216.0 if k == 0 else 1.0
    return a


def main():
    lengths = [0, 1, 2, 15, 16, 17, 31, 33, 1023, 1024, 1025, 2047, 2048, 2049, 3073, 5000]
    for kind in range(8):
        for n in lengths:
            a = make(kind, n)
            s = ta.sum(a)
            w = ta.sum(a, acc=ta.f64)
            print("kind%d" % kind, n, bits(s), bits(w), bits(sum(a)), s, w)
    for pos in [0, 1, 15, 16, 17, 1023, 1024, 1025, 2047, 2048, 2049]:
        n = 2100
        for what in range(5):
            a = ta.zeros(n, ta.f32)
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
                a[pos] = 3e38
                a[(pos + 5) % n] = 3e38
            print("pos%d_%d" % (pos, what), bits(ta.sum(a)), bits(ta.sum(a, ta.f64)), ta.sum(a))
    z = ta.array([-0.0, 0.0], ta.f32)
    print(bits(ta.sum(z)), bits(ta.sum(z[::-1])), bits(ta.sum(ta.full(17, -0.0, ta.f32))), bits(ta.sum(ta.zeros(17, ta.f32))))
    print(bits(ta.sum(ta.zeros(0, ta.f32))), bits(ta.sum(ta.full(1, -0.0, ta.f32))))
    t = ta.full(1025, 0.1, ta.f32)
    print(ta.sum(t), ta.sum(t, acc=ta.f64), sum(t))
    big = ta.full(5000, 16777216.0, ta.f32)
    print(ta.sum(big), ta.sum(big + 1.0), ta.sum(big + 1.0, acc=ta.f64))


main()
