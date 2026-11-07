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
        if ch < '0' or ch > '9':
            return False
    return True


def strip_zeros(s):
    i = 0
    L = len(s)
    while i + 1 < L and s[i] == '0':
        i += 1
    return s[i:]


def fmt(v):
    s = f"{v:.9f}"
    if s == "-0.000000000":
        return "0.000000000"
    return s


def main():
    av = sys.argv
    if len(av) != 4:
        return 1

    a = av[1]
    b = av[2]
    c = av[3]

    if not is_digits(a) or not is_digits(b) or not is_digits(c):
        return 1

    a = strip_zeros(a)
    b = strip_zeros(b)
    c = strip_zeros(c)

    if len(a) > 8:
        return 1
    n = int(a)
    if n < 1 or n > 10000000:
        return 1

    if len(b) > 7:
        return 1
    t = int(b)
    if t > 1000000:
        return 1

    if len(c) > 20:
        return 1

    x0 = 0
    x1 = 0
    x2 = 0
    x3 = 0

    for ch in c:
        dig = ord(ch) - 48

        v = x0 * 10
        x0 = v & 65535
        carry = v >> 16

        v = x1 * 10 + carry
        x1 = v & 65535
        carry = v >> 16

        v = x2 * 10 + carry
        x2 = v & 65535
        carry = v >> 16

        v = x3 * 10 + carry
        if v > 65535:
            return 1
        x3 = v

        v = x0 + dig
        x0 = v & 65535
        carry = v >> 16

        v = x1 + carry
        x1 = v & 65535
        carry = v >> 16

        v = x2 + carry
        x2 = v & 65535
        carry = v >> 16

        v = x3 + carry
        if v > 65535:
            return 1
        x3 = v

    h = [0.0] * n

    for i in range(n):
        o0 = x0
        o1 = x1
        o2 = x2
        o3 = x3

        k0 = o0 * A0 + C0
        k1 = o0 * A1 + o1 * A0 + C1
        k2 = o0 * A2 + o1 * A1 + o2 * A0 + C2
        k3 = o0 * A3 + o1 * A2 + o2 * A1 + o3 * A0 + C3

        x0 = k0 & 65535
        carry = k0 >> 16

        v = k1 + carry
        x1 = v & 65535
        carry = v >> 16

        v = k2 + carry
        x2 = v & 65535
        carry = v >> 16

        v = k3 + carry
        x3 = v & 65535

        q = ((x2 >> 1) + x3 * 32768) % 2001
        h[i] = (q - 1000) / 64.0

    sqrt = math.sqrt
    still = 0

    for s in range(1, t + 1):
        changed = False

        if s & 1:
            for i in range(n):
                if i == 0:
                    l = h[n - 1]
                else:
                    l = h[i - 1]

                j = i + 1
                if j < n:
                    r = h[j]
                else:
                    r = h[0]

                cv = h[i]
                d = (l + r) - (cv + cv)
                g = d / (1.0 + sqrt(d * d + 0.0625))
                nv = cv + 0.375 * g

                if nv != cv:
                    changed = True
                h[i] = nv
        else:
            for i in range(n - 1, -1, -1):
                if i == 0:
                    l = h[n - 1]
                else:
                    l = h[i - 1]

                j = i + 1
                if j < n:
                    r = h[j]
                else:
                    r = h[0]

                cv = h[i]
                d = (l + r) - (cv + cv)
                g = d / (1.0 + sqrt(d * d + 0.0625))
                nv = cv + 0.375 * g

                if nv != cv:
                    changed = True
                h[i] = nv

        if changed:
            still = 0
        else:
            still += 1
            if still >= 2:
                break

    total = 0.0
    energy = 0.0
    lo = h[0]
    hi = h[0]

    for i in range(n - 1):
        v = h[i]
        total = total + v
        tv = h[i + 1] - v
        energy = energy + tv * tv
        if v < lo:
            lo = v
        if v > hi:
            hi = v

    v = h[n - 1]
    total = total + v
    tv = h[0] - v
    energy = energy + tv * tv
    if v < lo:
        lo = v
    if v > hi:
        hi = v

    mid = h[n // 2]

    out = []
    out.append("sum " + fmt(total))
    out.append("energy " + fmt(energy))
    out.append("min " + fmt(lo))
    out.append("max " + fmt(hi))
    out.append("first " + fmt(h[0]))
    out.append("middle " + fmt(mid))
    out.append("last " + fmt(h[n - 1]))

    sys.stdout.write("\n".join(out) + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
