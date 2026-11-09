import sys
import math

DIG = "0123456789"


def parse_small(s, limit):
    if len(s) == 0:
        return -1
    v = 0
    for ch in s:
        k = DIG.find(ch)
        if k < 0:
            return -1
        v = v * 10 + k
        if v > limit:
            return -1
    return v


def parse_seed(s):
    if len(s) == 0:
        return None
    limbs = [0, 0, 0, 0]
    for ch in s:
        k = DIG.find(ch)
        if k < 0:
            return None
        carry = k
        for j in range(4):
            v = limbs[j] * 10 + carry
            limbs[j] = v & 0xFFFF
            carry = v >> 16
        if carry != 0:
            return None
    return limbs


def fmt(v):
    s = format(v, ".9f")
    if s[0] == "-":
        body = s[1:]
        zero = True
        for ch in body:
            if ch != "0" and ch != ".":
                zero = False
                break
        if zero:
            return body
    return s


def main():
    args = sys.argv[1:]
    if len(args) != 3:
        sys.exit(1)
    N = parse_small(args[0], 10000000)
    if N < 1:
        sys.exit(1)
    T = parse_small(args[1], 1000000)
    if T < 0:
        sys.exit(1)
    x = parse_seed(args[2])
    if x is None:
        sys.exit(1)

    A = 6364136223846793005
    C = 1442695040888963407
    a0 = A & 0xFFFF
    a1 = (A >> 16) & 0xFFFF
    a2 = (A >> 32) & 0xFFFF
    a3 = (A >> 48) & 0xFFFF
    c0 = C & 0xFFFF
    c1 = (C >> 16) & 0xFFFF
    c2 = (C >> 32) & 0xFFFF
    c3 = (C >> 48) & 0xFFFF

    h = [0.0] * N
    x0 = x[0]
    x1 = x[1]
    x2 = x[2]
    x3 = x[3]
    for i in range(N):
        p0 = x0 * a0
        p1 = x0 * a1 + x1 * a0
        p2 = x0 * a2 + x1 * a1 + x2 * a0
        p3 = x0 * a3 + x1 * a2 + x2 * a1 + x3 * a0
        t = p0 + c0
        x0 = t & 0xFFFF
        t = p1 + c1 + (t >> 16)
        x1 = t & 0xFFFF
        t = p2 + c2 + (t >> 16)
        x2 = t & 0xFFFF
        t = p3 + c3 + (t >> 16)
        x3 = t & 0xFFFF
        v = x3 * 32768 + (x2 >> 1)
        h[i] = float((v % 2001) - 1000) / 64.0

    for s in range(1, T + 1):
        if s % 2 == 1:
            for i in range(N):
                l = h[(i + N - 1) % N]
                r = h[(i + 1) % N]
                c = h[i]
                d = (l + r) - (c + c)
                g = d / (1.0 + math.sqrt(d * d + 0.0625))
                h[i] = c + 0.375 * g
        else:
            for i in range(N - 1, -1, -1):
                l = h[(i + N - 1) % N]
                r = h[(i + 1) % N]
                c = h[i]
                d = (l + r) - (c + c)
                g = d / (1.0 + math.sqrt(d * d + 0.0625))
                h[i] = c + 0.375 * g

    total = 0.0
    energy = 0.0
    mn = h[0]
    mx = h[0]
    for i in range(N):
        hi = h[i]
        total = total + hi
        t = h[(i + 1) % N] - hi
        energy = energy + t * t
        if hi < mn:
            mn = hi
        if hi > mx:
            mx = hi

    print("sum " + fmt(total))
    print("energy " + fmt(energy))
    print("min " + fmt(mn))
    print("max " + fmt(mx))
    print("first " + fmt(h[0]))
    print("middle " + fmt(h[N // 2]))
    print("last " + fmt(h[N - 1]))


main()
