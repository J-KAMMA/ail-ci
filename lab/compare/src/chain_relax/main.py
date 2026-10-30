import sys
from math import sqrt


def parse(s, lo, hi):
    if not s or not all('0' <= ch <= '9' for ch in s):
        return None
    v = int(s)
    if v < lo or v > hi:
        return None
    return v


def fmt(v):
    s = "%.9f" % v
    if s.startswith("-") and not any(ch in "123456789" for ch in s):
        s = s[1:]
    return s


def main():
    a = sys.argv[1:]
    if len(a) != 3:
        return 1
    n = parse(a[0], 1, 10000000)
    t = parse(a[1], 0, 1000000)
    seed = parse(a[2], 0, 18446744073709551615)
    if n is None or t is None or seed is None:
        return 1
    M = (1 << 64) - 1
    x = seed
    h = [0.0] * n
    for i in range(n):
        x = (x * 6364136223846793005 + 1442695040888963407) & M
        h[i] = float(((x >> 33) % 2001) - 1000) / 64.0
    for s in range(1, t + 1):
        if s & 1:
            for i in range(n - 1):
                c = h[i]
                d = (h[i - 1] + h[i + 1]) - (c + c)
                h[i] = c + 0.375 * (d / (1.0 + sqrt(d * d + 0.0625)))
            i = n - 1
            c = h[i]
            d = (h[i - 1] + h[0]) - (c + c)
            h[i] = c + 0.375 * (d / (1.0 + sqrt(d * d + 0.0625)))
        else:
            i = n - 1
            c = h[i]
            d = (h[i - 1] + h[0]) - (c + c)
            h[i] = c + 0.375 * (d / (1.0 + sqrt(d * d + 0.0625)))
            for i in range(n - 2, -1, -1):
                c = h[i]
                d = (h[i - 1] + h[i + 1]) - (c + c)
                h[i] = c + 0.375 * (d / (1.0 + sqrt(d * d + 0.0625)))
    total = 0.0
    energy = 0.0
    for i in range(n):
        total = total + h[i]
        tt = h[(i + 1) % n] - h[i]
        energy = energy + tt * tt
    out = [
        "sum " + fmt(total),
        "energy " + fmt(energy),
        "min " + fmt(min(h)),
        "max " + fmt(max(h)),
        "first " + fmt(h[0]),
        "middle " + fmt(h[n // 2]),
        "last " + fmt(h[n - 1]),
    ]
    sys.stdout.write("\n".join(out) + "\n")
    return 0


sys.exit(main())
