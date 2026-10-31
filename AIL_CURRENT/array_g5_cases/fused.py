import math
import ail_array as ta


def bits(x: float) -> str:
    return ta.array([x], ta.f64).tobytes().hex()


def digest(r: ta.Array[ta.f64]) -> str:
    n = len(r)
    if n <= 4100:
        data = r.tobytes()                       # every bit of every element
        h = 0
        for i in range(len(data)):
            h = (h * 31 + data[i]) % 1000000007
        return str(n) + ":" + str(h)
    # a large array: the ends, the middle and the fixed-order sum and dot (each of them a kernel of its own)
    return str(n) + ":" + bits(ta.sum(r)) + bits(r[0]) + bits(r[n // 2]) + bits(r[n - 1]) + bits(ta.dot(r, r))


def make(kind: int, n: int) -> ta.Array[ta.f64]:
    a = ta.zeros(n, ta.f64)
    seed = 777 + (kind % 16) * 104729
    for k in range(n):
        seed = (seed * 1103515245 + 12345) % 2147483648
        if kind == 0:
            a[k] = (seed % 2001 - 1000) / 7.0
        elif kind == 1:
            a[k] = (seed % 2001 - 1000) * 1e290
        elif kind == 2:
            a[k] = (seed % 2001 - 1000) * 1e-150
        elif kind == 3:
            a[k] = 0.1 * (k % 11)
        else:
            a[k] = (seed % 13 - 6) * 0.5
    return a


def chains(label: str, a: ta.Array[ta.f64], b: ta.Array[ta.f64], c: ta.Array[ta.f64], s: float):
    r1 = a * b + a
    r2 = (a + b) * (a - b) - c * 0.5
    r3 = 2.0 - a * b
    r4 = -(a * b) + c
    r5 = a * 3 + 1
    r6 = s * a - b * s + c
    r7 = a + b
    r8 = a - b
    r9 = a * b
    r10 = -a
    r11 = ((a * b + c) * a - b) * c + a * a * a
    print(label, digest(r1), digest(r2), digest(r3), digest(r4), digest(r5))
    print(label, digest(r6), digest(r7), digest(r8), digest(r9), digest(r10), digest(r11))


def main():
    lengths = [0, 1, 2, 63, 64, 65, 127, 128, 129, 255, 256, 257, 4095, 4096, 4097, 100003]
    for n in lengths:
        for kind in range(5):
            a = make(kind, n)
            b = make((kind + 1) % 5, n)
            c = make((kind + 2) % 5, n)
            chains("n%d_k%d" % (n, kind), a, b, c, 0.1 * kind - 0.2)
    # special values at chosen positions (the device flags NaN, subnormals and inf - inf: the CPU replay must give the same bits)
    specials = [math.inf, -math.inf, math.nan, -0.0, 0.0, 1e308, -1e308, 1e-310, 5e-324, 2.0 ** -1000, 1.5 * 2.0 ** -1000, 9007199254740993.0]
    for n in [65, 4097]:
        for pos in [0, 1, 63, 64, n - 1]:
            for i in range(len(specials)):
                a = make(0, n)
                b = make(3, n)
                c = make(4, n)
                a[pos] = specials[i]
                b[(pos + 7) % n] = specials[(i + 3) % len(specials)]
                c[(pos + 13) % n] = specials[(i + 5) % len(specials)]
                chains("sp%d_%d_%d" % (n, pos, i), a, b, c, specials[(i + 1) % len(specials)])
    # a program where the arrays are different lengths: the shape error comes first, with the same text
    x = ta.zeros(5, ta.f64)
    y = ta.zeros(6, ta.f64)
    z = ta.zeros(7, ta.f64)
    try:
        w = x * x + y * z
        print(digest(w))
    except ValueError as e:
        print("ValueError", e)
    try:
        w = x * y + z
        print(digest(w))
    except ValueError as e:
        print("ValueError", e)
    # scalars: NaN, inf and a python int
    u = make(0, 5000)
    print(digest(u * math.nan), digest(u + math.inf), digest(7 * u - 3), digest(u - u))


main()
