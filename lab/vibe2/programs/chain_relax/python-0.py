import sys
import math
from array import array

MASK64 = (1 << 64) - 1
MULT = 6364136223846793005
INC = 1442695040888963407
SQRT = math.sqrt


def sweep_odd(h, n):
    sqrt = SQRT

    c = h[0]
    l = h[n - 1]
    r = h[1]
    d = (l + r) - (c + c)
    g = d / (1.0 + sqrt(d * d + 0.0625))
    new = c + 0.375 * g
    h[0] = new

    first_new = new
    prev = new
    c_next = r

    for i in range(1, n - 1):
        c = c_next
        l = prev
        r = h[i + 1]

        d = (l + r) - (c + c)
        g = d / (1.0 + sqrt(d * d + 0.0625))
        new = c + 0.375 * g
        h[i] = new

        prev = new
        c_next = r

    c = c_next
    l = prev
    r = first_new

    d = (l + r) - (c + c)
    g = d / (1.0 + sqrt(d * d + 0.0625))
    h[n - 1] = c + 0.375 * g


def sweep_even(h, n):
    sqrt = SQRT

    c = h[n - 1]
    l = h[n - 2]
    r = h[0]
    d = (l + r) - (c + c)
    g = d / (1.0 + sqrt(d * d + 0.0625))
    new = c + 0.375 * g
    h[n - 1] = new

    rgt = new
    c_next = l

    for i in range(n - 2, 0, -1):
        c = c_next
        l = h[i - 1]
        r = rgt

        d = (l + r) - (c + c)
        g = d / (1.0 + sqrt(d * d + 0.0625))
        new = c + 0.375 * g
        h[i] = new

        rgt = new
        c_next = l

    c = c_next
    l = h[n - 1]
    r = rgt

    d = (l + r) - (c + c)
    g = d / (1.0 + sqrt(d * d + 0.0625))
    h[0] = c + 0.375 * g


def fixed9(v):
    s = format(v, ".9f")
    if s[0] == "-":
        ok = True
        for ch in s[1:]:
            if ch != "0" and ch != ".":
                ok = False
                break
        if ok:
            return s[1:]
    return s


def main():
    if len(sys.argv) != 4:
        return 1

    values = []
    for s in sys.argv[1:]:
        if not s:
            return 1

        for ch in s:
            if ch < "0" or ch > "9":
                return 1

        t = s.lstrip("0")
        if t == "":
            v = 0
        else:
            if len(t) > 20:
                return 1
            v = int(t)

        values.append(v)

    n, t_sweeps, seed = values

    if n < 1 or n > 10_000_000:
        return 1
    if t_sweeps < 0 or t_sweeps > 1_000_000:
        return 1
    if seed < 0 or seed > 18_446_744_073_709_551_615:
        return 1

    h = array("d", [0.0]) * n

    x = seed
    mult = MULT
    inc = INC
    mask = MASK64

    for i in range(n):
        x = (x * mult + inc) & mask
        h[i] = (((x >> 33) % 2001) - 1000) / 64.0

    if n > 1:
        for s in range(1, t_sweeps + 1):
            if s & 1:
                sweep_odd(h, n)
            else:
                sweep_even(h, n)

    total = 0.0
    energy = 0.0

    v = h[0]
    mn = v
    mx = v

    for i in range(n - 1):
        nxt = h[i + 1]

        total = total + v
        t = nxt - v
        energy = energy + t * t

        if v < mn:
            mn = v
        if v > mx:
            mx = v

        v = nxt

    total = total + v
    t = h[0] - v
    energy = energy + t * t

    if v < mn:
        mn = v
    if v > mx:
        mx = v

    out = [
        "sum " + fixed9(total),
        "energy " + fixed9(energy),
        "min " + fixed9(mn),
        "max " + fixed9(mx),
        "first " + fixed9(h[0]),
        "middle " + fixed9(h[n // 2]),
        "last " + fixed9(h[n - 1]),
    ]

    sys.stdout.write("\n".join(out) + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
