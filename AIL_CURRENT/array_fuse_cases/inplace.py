import math
import ail_array as ta


def bits(x: float) -> str:
    return ta.array([x], ta.f64).tobytes().hex()


def digest(r: ta.Array[ta.f64]) -> str:
    n = len(r)
    data = r.tobytes()
    h = 0
    for i in range(len(data)):
        h = (h * 31 + data[i]) % 1000000007
    return str(n) + ":" + str(h)


def make(kind: int, n: int) -> ta.Array[ta.f64]:
    a = ta.zeros(n, ta.f64)
    seed = 4242 + (kind % 16) * 104729
    for k in range(n):
        seed = (seed * 1103515245 + 12345) % 2147483648
        if kind == 0:
            a[k] = (seed % 2001 - 1000) / 7.0
        elif kind == 1:
            a[k] = (seed % 2001 - 1000) * 1e290
        elif kind == 2:
            a[k] = (seed % 2001 - 1000) * 1e-150
        elif kind == 3:
            a[k] = (seed % 5 - 2) * 1.0
        else:
            a[k] = (seed % 13 - 6) * 0.5
    return a


def updates(label: str, a0: ta.Array[ta.f64], b: ta.Array[ta.f64], c: ta.Array[ta.f64], s: float):
    a = a0.copy()
    a += b * c
    print(label, "1", digest(a))
    a = a0.copy()
    a -= b / c
    print(label, "2", digest(a))
    a = a0.copy()
    a *= b + c
    print(label, "3", digest(a))
    a = a0.copy()
    a /= abs(b) + 1.0
    print(label, "4", digest(a))
    a = a0.copy()
    a += s * b - c * s
    print(label, "5", digest(a))
    a = a0.copy()
    a += a * a                       # the target is also an operand: element k reads only element k
    print(label, "6", digest(a))
    a = a0.copy()
    a -= a * b + a
    print(label, "7", digest(a))
    a = a0.copy()
    a += ta.minimum(b, c) * s
    print(label, "8", digest(a))
    a = a0.copy()
    a /= c - c
    print(label, "9", digest(a))
    a = a0.copy()
    a += -b
    a *= -c * s
    print(label, "10", digest(a))


def main():
    lengths = [0, 1, 2, 15, 16, 17, 63, 64, 65, 255, 256, 257, 1023, 1024, 1025, 2049]
    for n in lengths:
        for kind in range(5):
            a = make(kind, n)
            b = make((kind + 1) % 5, n)
            c = make((kind + 2) % 5, n)
            updates("n%d_k%d" % (n, kind), a, b, c, 0.1 * kind - 0.2)
    specials = [math.inf, -math.inf, math.nan, -0.0, 0.0, 1e308, -1e308, 1e-310, 5e-324, 2.0 ** -1000, 1.5 * 2.0 ** -1000, 9007199254740993.0]
    for n in [65, 1025]:
        for pos in [0, 1, 15, 16, 17, 64, n - 1]:
            for i in range(len(specials)):
                a = make(0, n)
                b = make(3, n)
                c = make(4, n)
                a[pos] = specials[i]
                b[(pos + 7) % n] = specials[(i + 3) % len(specials)]
                c[(pos + 13) % n] = specials[(i + 5) % len(specials)]
                updates("sp%d_%d_%d" % (n, pos, i), a, b, c, specials[(i + 1) % len(specials)])
    # the same object under two names: both see the update
    p = make(0, 100)
    q = p
    q += make(3, 100) * make(4, 100)
    print("alias", digest(p), digest(q))
    # shape errors: the elements are not touched, and the text is the unfused code's
    x = make(0, 5)
    y = make(1, 6)
    t = make(2, 7)
    before = digest(x)
    try:
        x += y * t
    except ValueError as e:
        print("ValueError", e, before == digest(x))
    try:
        x += x * y
    except ValueError as e:
        print("ValueError", e, before == digest(x))
    v = make(0, 5)
    try:
        v -= v * y
    except ValueError as e:
        print("ValueError", e, digest(v))
    try:
        v /= abs(y) + v
    except ValueError as e:
        print("ValueError", e, digest(v))


main()
