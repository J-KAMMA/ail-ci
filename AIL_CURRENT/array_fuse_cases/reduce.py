import math
import ail_array as ta


def bits(x: float) -> str:
    return ta.array([x], ta.f64).tobytes().hex()


def make(kind: int, n: int) -> ta.Array[ta.f64]:
    a = ta.zeros(n, ta.f64)
    seed = 99 + (kind % 16) * 104729
    for k in range(n):
        seed = (seed * 1103515245 + 12345) % 2147483648
        if kind == 0:
            a[k] = 0.1 * (k % 11)
        elif kind == 1:
            a[k] = (seed % 2001 - 1000) / 7.0
        elif kind == 2:
            a[k] = 1.0 if k % 3 == 0 else (1e16 if k % 3 == 1 else -1e16)      # absorption and cancellation
        elif kind == 3:
            a[k] = (seed % 5 - 2) * 1.0
        elif kind == 4:
            a[k] = (seed % 2001 - 1000) * 1e290
        else:
            a[k] = 1.0 + 2.0 ** -52 * (seed % 3)
    return a


def reduces(label: str, a: ta.Array[ta.f64], b: ta.Array[ta.f64], c: ta.Array[ta.f64], s: float):
    r1 = ta.sum(a * b)
    r2 = ta.sum(a * b + c)
    r3 = ta.sum(a / c)
    r4 = ta.sum(abs(a) - b)
    r5 = ta.sum(ta.minimum(a, b) * s)
    r6 = ta.sum(ta.clip(a, -s, s) + c)
    print(label, bits(r1), bits(r2), bits(r3), bits(r4), bits(r5), bits(r6))
    d1 = ta.dot(a, b * c)
    d2 = ta.dot(a * b, c)
    d3 = ta.dot(a + b, b - c)
    d4 = ta.dot(a / b, c)
    d5 = ta.dot(a, b / c + s)
    d6 = ta.dot(ta.maximum(a, c), abs(b))
    print(label, bits(d1), bits(d2), bits(d3), bits(d4), bits(d5), bits(d6))
    e1 = ta.sum(-(a * b) * a - c)
    e2 = ta.dot(a, a) + ta.sum(a)
    print(label, bits(e1), bits(e2), repr(r1), repr(d1))


def main():
    lengths = [0, 1, 2, 15, 16, 17, 31, 32, 33, 1023, 1024, 1025, 1536, 2047, 2048, 2049, 3071, 3072, 3073, 4097, 5000]
    for n in lengths:
        for kind in range(6):
            a = make(kind, n)
            b = make((kind + 1) % 6, n)
            c = make((kind + 2) % 6, n)
            reduces("n%d_k%d" % (n, kind), a, b, c, 0.1 * kind - 0.2)
    specials = [math.inf, -math.inf, math.nan, -0.0, 0.0, 1e308, -1e308, 1e-310, 5e-324, 2.0 ** -1000, 1.5 * 2.0 ** -1000, 9007199254740993.0]
    positions = [0, 1, 15, 16, 17, 1023, 1024, 1025, 2047, 2048, 2049]
    for pos in positions:
        for i in range(len(specials)):
            a = make(1, 2100)
            b = make(3, 2100)
            c = make(5, 2100)
            a[pos] = specials[i]
            b[(pos + 5) % 2100] = specials[(i + 3) % len(specials)]
            c[(pos + 9) % 2100] = specials[(i + 5) % len(specials)]
            reduces("sp%d_%d" % (pos, i), a, b, c, specials[(i + 1) % len(specials)])
    # a long chain
    x = make(3, 3000)
    y = x * 0.5 + 0.25
    print(bits(ta.sum(((((x * 0.5 + 0.25) * x + 0.3) * x + 0.2) * x + 0.1) * x + 0.05)), bits(ta.dot(y, ((x * y + x) * y + x) * y + x)))
    # empty arrays and one element
    z = ta.zeros(0, ta.f64)
    print(bits(ta.sum(z * z + z)), bits(ta.dot(z + z, z * z)), bits(ta.sum(ta.array([-0.0], ta.f64) * 1.0)))
    # shape errors
    p = ta.zeros(5, ta.f64)
    q = ta.zeros(6, ta.f64)
    r = ta.zeros(7, ta.f64)
    try:
        print(bits(ta.sum(p * p + q * r)))
    except ValueError as e:
        print("ValueError", e)
    try:
        print(bits(ta.sum(p / q)))
    except ValueError as e:
        print("ValueError", e)
    try:
        print(bits(ta.dot(p, q * q)))
    except ValueError as e:
        print("ValueError", e)
    try:
        print(bits(ta.dot(p * p, q)))
    except ValueError as e:
        print("ValueError", e)
    try:
        print(bits(ta.dot(p + q, r - r)))
    except ValueError as e:
        print("ValueError", e)
    try:
        print(bits(ta.dot(p * p, p * q)))
    except ValueError as e:
        print("ValueError", e)


main()
