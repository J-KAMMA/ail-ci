import sys
import math
from array import array


def parse_bounded(s, hi):
    if not s:
        return None
    for ch in s:
        if ch < '0' or ch > '9':
            return None
    t = s.lstrip('0')
    if not t:
        t = '0'
    hs = str(hi)
    if len(t) > len(hs):
        return None
    if len(t) == len(hs) and t > hs:
        return None
    return int(t)


def format_value(v):
    s = format(v, ".9f")
    body = s[1:] if s.startswith("-") else s
    if body.strip("0.") == "":
        return "0.000000000"
    return s


def main():
    if len(sys.argv) != 4:
        sys.exit(1)

    n = parse_bounded(sys.argv[1], 10000000)
    t = parse_bounded(sys.argv[2], 1000000)
    seed = parse_bounded(sys.argv[3], 18446744073709551615)

    if n is None or t is None or seed is None or n < 1:
        sys.exit(1)

    mask = (1 << 64) - 1
    h = array("d", [0.0]) * n

    x = seed
    for i in range(n):
        x = (x * 6364136223846793005 + 1442695040888963407) & mask
        h[i] = ((((x >> 33) % 2001) - 1000) / 64.0)

    if t > 0 and n > 1:
        sqrt = math.sqrt

        for sweep in range(1, t + 1):
            changed = False

            if sweep & 1:
                i = 0
                step = 1
                stop = n
            else:
                i = n - 1
                step = -1
                stop = -1

            while i != stop:
                c = h[i]

                if i == 0:
                    l = h[n - 1]
                else:
                    l = h[i - 1]

                if i + 1 == n:
                    r = h[0]
                else:
                    r = h[i + 1]

                d = (l + r) - (c + c)
                g = d / (1.0 + sqrt(d * d + 0.0625))
                nv = c + 0.375 * g

                if nv != c:
                    changed = True

                h[i] = nv
                i += step

            if not changed:
                break

    total = 0.0
    energy = 0.0
    mn = h[0]
    mx = h[0]

    for i in range(n):
        v = h[i]
        total = total + v

        if i + 1 < n:
            w = h[i + 1]
        else:
            w = h[0]

        diff = w - v
        energy = energy + diff * diff

        if v < mn:
            mn = v
        if v > mx:
            mx = v

    lines = [
        "sum " + format_value(total),
        "energy " + format_value(energy),
        "min " + format_value(mn),
        "max " + format_value(mx),
        "first " + format_value(h[0]),
        "middle " + format_value(h[n // 2]),
        "last " + format_value(h[n - 1]),
    ]

    sys.stdout.write("\n".join(lines) + "\n")


if __name__ == "__main__":
    main()
