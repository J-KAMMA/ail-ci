import sys
import math


def parse_uint(s, minv, maxv):
    if not s or any(ch not in "0123456789" for ch in s):
        return None
    v = int(s)
    if v < minv or v > maxv:
        return None
    return v


def fmt(v):
    s = "%.9f" % v
    if s == "-0.000000000":
        s = "0.000000000"
    return s


def main():
    args = sys.argv[1:]
    if len(args) != 3:
        sys.exit(1)

    N = parse_uint(args[0], 1, 10000000)
    T = parse_uint(args[1], 0, 1000000)
    SEED = parse_uint(args[2], 0, 18446744073709551615)
    if N is None or T is None or SEED is None:
        sys.exit(1)

    MASK = (1 << 64) - 1
    A = 6364136223846793005
    C = 1442695040888963407

    x = SEED
    h = [0.0] * N
    for i in range(N):
        x = (x * A + C) & MASK
        h[i] = float(((x >> 33) % 2001) - 1000) / 64.0

    sqrt = math.sqrt
    for s in range(1, T + 1):
        if s % 2 == 1:
            for i in range(N):
                l = h[i - 1]
                r = h[i + 1] if i + 1 < N else h[0]
                c = h[i]
                d = (l + r) - (c + c)
                g = d / (1.0 + sqrt(d * d + 0.0625))
                h[i] = c + 0.375 * g
        else:
            for i in range(N - 1, -1, -1):
                l = h[i - 1]
                r = h[i + 1] if i + 1 < N else h[0]
                c = h[i]
                d = (l + r) - (c + c)
                g = d / (1.0 + sqrt(d * d + 0.0625))
                h[i] = c + 0.375 * g

    total = 0.0
    energy = 0.0
    for i in range(N):
        total = total + h[i]
        t = h[(i + 1) % N] - h[i]
        energy = energy + t * t

    lo = min(h)
    hi = max(h)

    out = []
    out.append("sum " + fmt(total) + "\n")
    out.append("energy " + fmt(energy) + "\n")
    out.append("min " + fmt(lo) + "\n")
    out.append("max " + fmt(hi) + "\n")
    out.append("first " + fmt(h[0]) + "\n")
    out.append("middle " + fmt(h[N // 2]) + "\n")
    out.append("last " + fmt(h[N - 1]) + "\n")
    sys.stdout.write("".join(out))
    sys.exit(0)


if __name__ == "__main__":
    main()
