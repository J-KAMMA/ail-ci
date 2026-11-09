import sys
import math

DIG = "0123456789"

def all_digits(s):
    if len(s) == 0:
        return False
    for ch in s:
        if ch not in DIG:
            return False
    return True

def small_int(s):
    # s is all digits. Returns -1 if the value is too large for any valid range.
    t = s.lstrip("0")
    if len(t) > 9:
        return -1
    if t == "":
        return 0
    return int(t)

def parse_seed(s):
    # Parse decimal into four 16-bit limbs (little endian); None if > 2^64 - 1.
    x = [0, 0, 0, 0]
    for ch in s:
        carry = ord(ch) - 48
        for k in range(4):
            v = x[k] * 10 + carry
            x[k] = v & 65535
            carry = v >> 16
        if carry != 0:
            return None
    return x

A = 6364136223846793005
C = 1442695040888963407
AL = [A & 65535, (A >> 16) & 65535, (A >> 32) & 65535, (A >> 48) & 65535]
CL = [C & 65535, (C >> 16) & 65535, (C >> 32) & 65535, (C >> 48) & 65535]

def lcg_step(x):
    # x = (x * A + C) mod 2^64, computed on 16-bit limbs to stay within int64.
    out = [0, 0, 0, 0]
    carry = 0
    for k in range(4):
        s = carry + CL[k]
        for i in range(k + 1):
            s += x[i] * AL[k - i]
        out[k] = s & 65535
        carry = s >> 16
    return out

def fmt(v):
    s = "%.9f" % v
    if s.lstrip("-").strip("0.") == "":
        return "0.000000000"
    return s

def main():
    args = sys.argv[1:]
    if len(args) != 3:
        sys.exit(1)
    for a in args:
        if not all_digits(a):
            sys.exit(1)
    n = small_int(args[0])
    t = small_int(args[1])
    if n < 1 or n > 10000000:
        sys.exit(1)
    if t < 0 or t > 1000000:
        sys.exit(1)
    seed = parse_seed(args[2])
    if seed is None:
        sys.exit(1)

    x = seed
    h = [0.0] * n
    for i in range(n):
        x = lcg_step(x)
        v = (x[3] << 15) | (x[2] >> 1)
        q = v % 2001
        h[i] = float(q - 1000) / 64.0

    for s in range(1, t + 1):
        if s % 2 == 1:
            idx = range(n)
        else:
            idx = range(n - 1, -1, -1)
        for i in idx:
            il = (i + n - 1) % n
            ir = (i + 1) % n
            l = h[il]
            r = h[ir]
            c = h[i]
            d = (l + r) - (c + c)
            g = d / (1.0 + math.sqrt(d * d + 0.0625))
            h[i] = c + 0.375 * g

    total = 0.0
    energy = 0.0
    for i in range(n):
        total = total + h[i]
        tt = h[(i + 1) % n] - h[i]
        energy = energy + tt * tt

    mn = h[0]
    mx = h[0]
    for i in range(1, n):
        if h[i] < mn:
            mn = h[i]
        if h[i] > mx:
            mx = h[i]

    out = []
    out.append("sum " + fmt(total) + "\n")
    out.append("energy " + fmt(energy) + "\n")
    out.append("min " + fmt(mn) + "\n")
    out.append("max " + fmt(mx) + "\n")
    out.append("first " + fmt(h[0]) + "\n")
    out.append("middle " + fmt(h[n // 2]) + "\n")
    out.append("last " + fmt(h[n - 1]) + "\n")
    sys.stdout.write("".join(out))
    sys.exit(0)

main()
