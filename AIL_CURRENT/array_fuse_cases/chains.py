import math
import ail_array as ta


def bits(x: float) -> str:
    return ta.array([x], ta.f64).tobytes().hex()


def digest(r: ta.Array[ta.f64]) -> str:
    n = len(r)
    data = r.tobytes()                           # every bit of every element
    h = 0
    for i in range(len(data)):
        h = (h * 31 + data[i]) % 1000000007
    return str(n) + ":" + str(h)


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
            a[k] = (seed % 5 - 2) * 1.0          # small integers: zeros, ties, equal operands
        else:
            a[k] = (seed % 13 - 6) * 0.5
    return a


def chains(label: str, a: ta.Array[ta.f64], b: ta.Array[ta.f64], c: ta.Array[ta.f64], s: float):
    r1 = a * b / c + a
    r2 = (a + b) / (c - a)
    r3 = s / a - b
    r4 = a / s + c * b
    r5 = (a / b) / (c / a)
    r6 = -(a / b) * c
    print(label, digest(r1), digest(r2), digest(r3), digest(r4), digest(r5), digest(r6))
    r7 = abs(a - b) * c
    r8 = -abs(a / (b - c))
    r9 = abs(abs(a) - b) + abs(c)
    r10 = ta.minimum(a, b) + ta.maximum(b, c) * a
    r11 = ta.minimum(a, s) - ta.maximum(a, -s)
    r12 = ta.minimum(a / b, c)
    r13 = ta.maximum(ta.minimum(a, b), c)
    print(label, digest(r7), digest(r8), digest(r9), digest(r10), digest(r11), digest(r12), digest(r13))
    r14 = ta.clip(a * b, -s, 1.5 * s) + c
    r15 = ta.clip(a, b, c)
    r16 = ta.clip(a + b, -s, s) * ta.clip(c, -2.0, 2.0)
    r17 = a / 0.0 + b / -0.0
    r18 = 0.0 / a - c
    r19 = (a - a) / (b - b)
    r20 = a * 1e308 / (b * 1e308) + a / 1e-310
    print(label, digest(r14), digest(r15), digest(r16), digest(r17), digest(r18), digest(r19), digest(r20))


def main():
    lengths = [0, 1, 2, 15, 16, 17, 63, 64, 65, 255, 256, 257, 1023, 1024, 1025, 2049]
    for n in lengths:
        for kind in range(5):
            a = make(kind, n)
            b = make((kind + 1) % 5, n)
            c = make((kind + 2) % 5, n)
            chains("n%d_k%d" % (n, kind), a, b, c, 0.1 * kind - 0.2)
    # special values at chosen positions: inf, NaN, signed zeros, the largest and the smallest numbers, a number past 2**53
    specials = [math.inf, -math.inf, math.nan, -0.0, 0.0, 1e308, -1e308, 1e-310, 5e-324, 2.0 ** -1000, 1.5 * 2.0 ** -1000, 9007199254740993.0]
    for n in [65, 1025]:
        for pos in [0, 1, 15, 16, 17, 63, 64, n - 1]:
            for i in range(len(specials)):
                a = make(0, n)
                b = make(3, n)
                c = make(4, n)
                a[pos] = specials[i]
                b[(pos + 7) % n] = specials[(i + 3) % len(specials)]
                c[(pos + 13) % n] = specials[(i + 5) % len(specials)]
                chains("sp%d_%d_%d" % (n, pos, i), a, b, c, specials[(i + 1) % len(specials)])
    # the scalar is itself special: every element sees it
    for i in range(len(specials)):
        a = make(0, 100)
        b = make(3, 100)
        c = make(4, 100)
        chains("sc%d" % i, a, b, c, specials[i])
    # signed zeros and NaN through minimum / maximum / clip: the order of -0.0 and 0.0, and a NaN in either operand
    z = ta.array([0.0, -0.0, 0.0, -0.0, math.nan, 1.0, math.nan, -1.0], ta.f64)
    w = ta.array([-0.0, 0.0, 0.0, -0.0, 1.0, math.nan, math.nan, -1.0], ta.f64)
    for s in [0.0, -0.0, math.nan, 1.0]:
        print("zero", s, digest(ta.minimum(z, w) * 1.0), digest(ta.maximum(z, w) * 1.0), digest(ta.minimum(z, s) + w),
              digest(ta.maximum(z, s) + w), digest(ta.clip(z + w, s, 2.0) - w), digest(ta.clip(z + w, -2.0, s) - w))
    # shape errors: the first failing check, with the text of the unfused code
    x = ta.zeros(5, ta.f64)
    y = ta.zeros(6, ta.f64)
    t = ta.zeros(7, ta.f64)
    try:
        w2 = x / x + y / t
        print(digest(w2))
    except ValueError as e:
        print("ValueError", e)
    try:
        w2 = ta.minimum(x, y) + t * t
        print(digest(w2))
    except ValueError as e:
        print("ValueError", e)
    try:
        w2 = abs(x - x) / y
        print(digest(w2))
    except ValueError as e:
        print("ValueError", e)
    try:
        w2 = ta.clip(x * y, 0.0, 1.0) + x
        print(digest(w2))
    except ValueError as e:
        print("ValueError", e)


main()
