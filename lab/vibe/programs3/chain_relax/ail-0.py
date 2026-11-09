import sys
import math

A0 = 32557
A1 = 19605
A2 = 62509
A3 = 22609
C0 = 33103
C1 = 63335
C2 = 31614
C3 = 5125


def is_digits(s):
    if len(s) == 0:
        return False
    for ch in s:
        if ch < "0" or ch > "9":
            return False
    return True


def parse_small(s, lo, hi):
    t = s.lstrip("0")
    if t == "":
        v = 0
    else:
        if len(t) > 18:
            return None
        v = int(t)
    if v < lo or v > hi:
        return None
    return v


def parse_seed(s):
    limbs = [0, 0, 0, 0]
    for ch in s:
        carry = ord(ch) - 48
        for k in range(4):
            v = limbs[k] * 10 + carry
            limbs[k] = v & 65535
            carry = v >> 16
        if carry != 0:
            return None
    return limbs


def fmt(v):
    s = "%.9f" % v
    if s == "-0.000000000":
        return "0.000000000"
    return s


def main():
    if len(sys.argv) != 4:
        sys.exit(1)
    a1 = sys.argv[1]
    a2 = sys.argv[2]
    a3 = sys.argv[3]
    if not is_digits(a1) or not is_digits(a2) or not is_digits(a3):
        sys.exit(1)
    n = parse_small(a1, 1, 10000000)
    if n is None:
        sys.exit(1)
    t_sweeps = parse_small(a2, 0, 1000000)
    if t_sweeps is None:
        sys.exit(1)
    limbs = parse_seed(a3)
    if limbs is None:
        sys.exit(1)

    x0 = limbs[0]
    x1 = limbs[1]
    x2 = limbs[2]
    x3 = limbs[3]

    N = n
    h = [0.0] * N
    for i in range(N):
        t = x0 * A0 + C0
        nx0 = t & 65535
        carry = t >> 16
        t = x0 * A1 + x1 * A0 + carry + C1
        nx1 = t & 65535
        carry = t >> 16
        t = x0 * A2 + x1 * A1 + x2 * A0 + carry + C2
        nx2 = t & 65535
        carry = t >> 16
        t = x0 * A3 + x1 * A2 + x2 * A1 + x3 * A0 + carry + C3
        nx3 = t & 65535
        x0 = nx0
        x1 = nx1
        x2 = nx2
        x3 = nx3
        hi = x2 + (x3 << 16)
        v = ((hi >> 1) % 2001) - 1000
        h[i] = v / 64.0

    sqrt = math.sqrt
    T = t_sweeps
    for s in range(1, T + 1):
        changed = False
        if s & 1:
            prev = h[N - 1]
            for i in range(N):
                c = h[i]
                if i + 1 < N:
                    r = h[i + 1]
                else:
                    r = h[0]
                d = (prev + r) - (c + c)
                g = d / (1.0 + sqrt(d * d + 0.0625))
                nc = c + 0.375 * g
                if nc != c:
                    changed = True
                h[i] = nc
                prev = nc
        else:
            nxt = h[0]
            for i in range(N - 1, -1, -1):
                c = h[i]
                if i > 0:
                    l = h[i - 1]
                else:
                    l = h[N - 1]
                d = (l + nxt) - (c + c)
                g = d / (1.0 + sqrt(d * d + 0.0625))
                nc = c + 0.375 * g
                if nc != c:
                    changed = True
                h[i] = nc
                nxt = nc
        if not changed:
            break

    total = 0.0
    energy = 0.0
    mn = h[0]
    mx = h[0]
    for i in range(N):
        c = h[i]
        total = total + c
        if i == N - 1:
            r = h[0]
        else:
            r = h[i + 1]
        t = r - c
        energy = energy + t * t
        if c < mn:
            mn = c
        if c > mx:
            mx = c

    mid = h[N // 2]
    out = []
    out.append("sum " + fmt(total))
    out.append("energy " + fmt(energy))
    out.append("min " + fmt(mn))
    out.append("max " + fmt(mx))
    out.append("first " + fmt(h[0]))
    out.append("middle " + fmt(mid))
    out.append("last " + fmt(h[N - 1]))
    sys.stdout.write("\n".join(out) + "\n")


main()
