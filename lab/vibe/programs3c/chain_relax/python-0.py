import sys
import math


def parse_uint(text):
    if not text or any(ch not in "0123456789" for ch in text):
        return None
    return int(text)


def fmt(v):
    s = "%.9f" % v
    body = s.lstrip("-")
    if body.strip("0.") == "":
        return "0.000000000"
    return s


def main():
    args = sys.argv[1:]
    if len(args) != 3:
        sys.exit(1)

    n = parse_uint(args[0])
    t = parse_uint(args[1])
    seed = parse_uint(args[2])

    if n is None or t is None or seed is None:
        sys.exit(1)
    if not (1 <= n <= 10000000):
        sys.exit(1)
    if not (0 <= t <= 1000000):
        sys.exit(1)
    if not (0 <= seed <= 18446744073709551615):
        sys.exit(1)

    mask = (1 << 64) - 1
    mul = 6364136223846793005
    add = 1442695040888963407

    x = seed
    h = [0.0] * n
    for i in range(n):
        x = (x * mul + add) & mask
        h[i] = float(((x >> 33) % 2001) - 1000) / 64.0

    sqrt = math.sqrt
    fwd = range(n)
    bwd = range(n - 1, -1, -1)

    for s in range(1, t + 1):
        order = fwd if (s & 1) else bwd
        for i in order:
            l = h[(i + n - 1) % n]
            r = h[(i + 1) % n]
            c = h[i]
            d = (l + r) - (c + c)
            g = d / (1.0 + sqrt(d * d + 0.0625))
            h[i] = c + 0.375 * g

    total = 0.0
    energy = 0.0
    for i in range(n):
        total = total + h[i]
        diff = h[(i + 1) % n] - h[i]
        energy = energy + diff * diff

    lo = min(h)
    hi = max(h)

    out = []
    out.append("sum " + fmt(total) + "\n")
    out.append("energy " + fmt(energy) + "\n")
    out.append("min " + fmt(lo) + "\n")
    out.append("max " + fmt(hi) + "\n")
    out.append("first " + fmt(h[0]) + "\n")
    out.append("middle " + fmt(h[n // 2]) + "\n")
    out.append("last " + fmt(h[n - 1]) + "\n")
    sys.stdout.write("".join(out))
    sys.exit(0)


if __name__ == "__main__":
    main()
