import sys
import math
from array import array


def main():
    args = sys.argv[1:]
    if len(args) != 3:
        return 1

    for arg in args:
        if not arg:
            return 1
        for ch in arg:
            if ch < '0' or ch > '9':
                return 1

    try:
        n = int(args[0])
        t = int(args[1])
        seed = int(args[2])
    except ValueError:
        return 1

    if not (1 <= n <= 10000000):
        return 1
    if not (0 <= t <= 1000000):
        return 1
    if not (0 <= seed <= 18446744073709551615):
        return 1

    h = array('d', [0.0]) * n

    x = seed
    mask = (1 << 64) - 1
    mul = 6364136223846793005
    inc = 1442695040888963407

    for i in range(n):
        x = (x * mul + inc) & mask
        h[i] = (((x >> 33) % 2001) - 1000) / 64.0

    if t and n > 1:
        sqrt = math.sqrt

        for sweep in range(1, t + 1):
            changed = False

            if sweep & 1:
                c = h[0]
                l = h[n - 1]
                r = h[1]
                d = (l + r) - (c + c)
                g = d / (1.0 + sqrt(d * d + 0.0625))
                new = c + 0.375 * g
                if new != c:
                    changed = True
                h[0] = new

                for i in range(1, n - 1):
                    c = h[i]
                    d = (h[i - 1] + h[i + 1]) - (c + c)
                    g = d / (1.0 + sqrt(d * d + 0.0625))
                    new = c + 0.375 * g
                    if new != c:
                        changed = True
                    h[i] = new

                i = n - 1
                c = h[i]
                l = h[i - 1]
                r = h[0]
                d = (l + r) - (c + c)
                g = d / (1.0 + sqrt(d * d + 0.0625))
                new = c + 0.375 * g
                if new != c:
                    changed = True
                h[i] = new
            else:
                i = n - 1
                c = h[i]
                l = h[i - 1]
                r = h[0]
                d = (l + r) - (c + c)
                g = d / (1.0 + sqrt(d * d + 0.0625))
                new = c + 0.375 * g
                if new != c:
                    changed = True
                h[i] = new

                for i in range(n - 2, 0, -1):
                    c = h[i]
                    d = (h[i - 1] + h[i + 1]) - (c + c)
                    g = d / (1.0 + sqrt(d * d + 0.0625))
                    new = c + 0.375 * g
                    if new != c:
                        changed = True
                    h[i] = new

                c = h[0]
                l = h[n - 1]
                r = h[1]
                d = (l + r) - (c + c)
                g = d / (1.0 + sqrt(d * d + 0.0625))
                new = c + 0.375 * g
                if new != c:
                    changed = True
                h[0] = new

            if not changed:
                break

    total = 0.0
    energy = 0.0
    minimum = h[0]
    maximum = h[0]

    for i in range(n - 1):
        c = h[i]
        total = total + c
        if c < minimum:
            minimum = c
        if c > maximum:
            maximum = c

        diff = h[i + 1] - c
        energy = energy + diff * diff

    c = h[n - 1]
    total = total + c
    if c < minimum:
        minimum = c
    if c > maximum:
        maximum = c

    diff = h[0] - c
    energy = energy + diff * diff

    def fmt(value):
        text = format(value, ".9f")
        if text == "-0.000000000":
            text = "0.000000000"
        return text

    output = (
        "sum " + fmt(total) + "\n"
        "energy " + fmt(energy) + "\n"
        "min " + fmt(minimum) + "\n"
        "max " + fmt(maximum) + "\n"
        "first " + fmt(h[0]) + "\n"
        "middle " + fmt(h[n // 2]) + "\n"
        "last " + fmt(h[n - 1]) + "\n"
    )

    sys.stdout.write(output)
    return 0


if __name__ == "__main__":
    sys.exit(main())
