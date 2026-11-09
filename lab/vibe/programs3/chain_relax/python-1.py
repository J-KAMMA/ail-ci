import sys
import math
from array import array


def parse_dec(s, lo, hi):
    if not s:
        return None
    for ch in s:
        if ch < '0' or ch > '9':
            return None

    t = s.lstrip('0')
    if not t:
        v = 0
    else:
        if len(t) > len(str(hi)):
            return None
        v = int(t)

    if v < lo or v > hi:
        return None
    return v


def fmt(v):
    s = format(v, ".9f")
    if s == "-0.000000000":
        return "0.000000000"
    return s


def main():
    args = sys.argv[1:]
    if len(args) != 3:
        return 1

    n = parse_dec(args[0], 1, 10000000)
    t = parse_dec(args[1], 0, 1000000)
    seed = parse_dec(args[2], 0, 18446744073709551615)

    if n is None or t is None or seed is None:
        return 1

    mask = 0xFFFFFFFFFFFFFFFF
    mul = 6364136223846793005
    inc = 1442695040888963407

    h = array('d')
    append = h.append
    x = seed

    for _ in range(n):
        x = (x * mul + inc) & mask
        append((((x >> 33) % 2001) - 1000) / 64.0)

    if t > 0 and n > 1:
        sqrt = math.sqrt

        for s in range(1, t + 1):
            if s & 1:
                left = h[n - 1]
                for i in range(n):
                    c = h[i]
                    r = h[i + 1] if i + 1 < n else h[0]
                    d = (left + r) - (c + c)
                    g = d / (1.0 + sqrt(d * d + 0.0625))
                    v = c + 0.375 * g
                    h[i] = v
                    left = v
            else:
                right = h[0]
                for i in range(n - 1, -1, -1):
                    c = h[i]
                    l = h[i - 1] if i > 0 else h[n - 1]
                    d = (l + right) - (c + c)
                    g = d / (1.0 + sqrt(d * d + 0.0625))
                    v = c + 0.375 * g
                    h[i] = v
                    right = v

    total = 0.0
    energy = 0.0
    mn = h[0]
    mx = h[0]

    for i in range(n):
        v = h[i]
        total = total + v

        nxt = h[i + 1] if i + 1 < n else h[0]
        diff = nxt - v
        energy = energy + diff * diff

        if v < mn:
            mn = v
        elif v > mx:
            mx = v

    middle = h[n // 2]

    out = (
        "sum " + fmt(total) + "\n"
        "energy " + fmt(energy) + "\n"
        "min " + fmt(mn) + "\n"
        "max " + fmt(mx) + "\n"
        "first " + fmt(h[0]) + "\n"
        "middle " + fmt(middle) + "\n"
        "last " + fmt(h[n - 1]) + "\n"
    )
    sys.stdout.write(out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
