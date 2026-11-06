import math
import ail_array as ta


def bits(x: float) -> str:
    return ta.array([x], ta.f64).tobytes().hex()


def make(kind: int, n: int) -> ta.Array[ta.f32]:
    a = ta.zeros(n, ta.f32)
    seed = 99 + kind * 104729
    for k in range(n):
        seed = (seed * 1103515245 + 12345) % 2147483648
        if kind == 0:
            a[k] = 0.1 * k
        elif kind == 1:
            a[k] = (seed % 2001 - 1000) / 3.0
        elif kind == 2:
            a[k] = 1.0 / (k + 1)
        elif kind == 3:
            a[k] = -0.0 if k % 2 == 0 else 0.0
        elif kind == 4:
            a[k] = 1e19 if k % 2 == 0 else -1e19
        elif kind == 5:
            a[k] = (seed % 1000) * 1e-23
        else:
            a[k] = 1.0 + (seed % 100) * 1.1920928955078125e-07
    return a


def main():
    lengths = [0, 1, 2, 15, 16, 17, 31, 33, 1023, 1024, 1025, 2047, 2048, 2049, 3073, 5000]
    for kind in range(7):
        for n in lengths:
            a = make(kind, n)
            b = make((kind + 2) % 7, n)
            d = ta.dot(a, b)
            w = ta.dot(a, b, acc=ta.f64)
            print("kind%d" % kind, n, bits(d), bits(w), bits(ta.sum(a * b)), d, w)
    for pos in [0, 15, 16, 17, 1023, 1024, 1025, 2048]:
        n = 2100
        for what in range(4):
            a = make(1, n)
            b = make(6, n)
            if what == 0:
                a[pos] = math.inf
            elif what == 1:
                b[pos] = math.nan
            elif what == 2:
                a[pos] = math.inf
                b[pos] = 0.0
            else:
                a[pos] = 1e30
                b[pos] = 1e30
            print("pos%d_%d" % (pos, what), bits(ta.dot(a, b)), bits(ta.dot(a, b, acc=ta.f64)))
    x = ta.array([1e-30, 1e-30, 3e38, 2.0], ta.f32)
    y = ta.array([1e-30, -1e-30, 2.0, -3e38], ta.f32)
    print(bits(ta.dot(x, y)), bits(ta.dot(x, y, acc=ta.f64)), bits(ta.dot(x, x)))
    m = ta.array([-0.0], ta.f32)
    print(bits(ta.dot(m, ta.array([1.0], ta.f32))), bits(ta.dot(m, m)), bits(ta.dot(ta.zeros(0, ta.f32), ta.zeros(0, ta.f32))))


main()
