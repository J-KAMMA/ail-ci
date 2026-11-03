from ail import wrapping_add, wrapping_mul
import sys

def digits_only(s: str) -> bool:
    if len(s) == 0:
        return False
    for ch in s:
        if ch < '0' or ch > '9':
            return False
    return True

def strip0(s: str) -> str:
    i = 0
    while i < len(s) - 1 and s[i] == '0':
        i += 1
    return s[i:]

def fmt(v: float) -> str:
    s = '%.9f' % v
    if s[0] == '-':
        allz = True
        for ch in s[1:]:
            if ch != '0' and ch != '.':
                allz = False
        if allz:
            return s[1:]
    return s

def main() -> int:
    if len(sys.argv) != 4:
        return 1
    a = sys.argv[1]
    b = sys.argv[2]
    c = sys.argv[3]
    if not digits_only(a) or not digits_only(b) or (not digits_only(c)):
        return 1
    a = strip0(a)
    b = strip0(b)
    c = strip0(c)
    if len(a) > 8 or len(b) > 8:
        return 1
    n = int(a)
    t = int(b)
    if n < 1 or n > 10000000 or t > 1000000:
        return 1
    if len(c) > 20:
        return 1
    if len(c) == 20 and c > '18446744073709551615':
        return 1
    x = 0
    for ch in c:
        x = wrapping_add(wrapping_mul(x, 10), ord(ch) - 48)
    h = [0.0] * n
    for i in range(n):
        x = wrapping_add(wrapping_mul(x, 6364136223846793005), 1442695040888963407)
        m = x >> 33 & 2147483647
        h[i] = float(m % 2001 - 1000) / 64.0
    for s in range(1, t + 1):
        if s % 2 == 1:
            for i in range(n):
                li = i - 1
                if li < 0:
                    li = n - 1
                ri = i + 1
                if ri == n:
                    ri = 0
                l = h[li]
                r = h[ri]
                cc = h[i]
                d = l + r - (cc + cc)
                g = d / (1.0 + (d * d + 0.0625) ** 0.5)
                h[i] = cc + 0.375 * g
        else:
            for k in range(n):
                i = n - 1 - k
                li = i - 1
                if li < 0:
                    li = n - 1
                ri = i + 1
                if ri == n:
                    ri = 0
                l = h[li]
                r = h[ri]
                cc = h[i]
                d = l + r - (cc + cc)
                g = d / (1.0 + (d * d + 0.0625) ** 0.5)
                h[i] = cc + 0.375 * g
    sum = 0.0
    energy = 0.0
    mn = h[0]
    mx = h[0]
    for i in range(n):
        v = h[i]
        sum = sum + v
        ri = i + 1
        if ri == n:
            ri = 0
        tt = h[ri] - v
        energy = energy + tt * tt
        if v < mn:
            mn = v
        if v > mx:
            mx = v
    print('sum ' + fmt(sum))
    print('energy ' + fmt(energy))
    print('min ' + fmt(mn))
    print('max ' + fmt(mx))
    print('first ' + fmt(h[0]))
    print('middle ' + fmt(h[n // 2]))
    print('last ' + fmt(h[n - 1]))
    return 0

if __name__ == "__main__":
    sys.exit(main())
