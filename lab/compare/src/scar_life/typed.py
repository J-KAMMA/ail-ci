from ail import read_stdin_bytes, write_stdout_bytes
import sys

def code(c: int) -> int:
    if c >= ord('0') and c <= ord('9'):
        return c - ord('0')
    if c == ord('A'):
        return 10
    if c == ord('B'):
        return 11
    if c == ord('C'):
        return 12
    return -1

class Rule:

    def __init__(self, bs: list[int], ss: list[int]):
        self.bs = bs
        self.ss = ss

def parse_rule(r: bytes, ru: Rule) -> bool:
    n = len(r)
    if n < 3 or r[0] != ord('B'):
        return False
    i = 1
    prev = -1
    while i < n and r[i] != ord('/'):
        c = code(r[i])
        if c < 0 or c <= prev:
            return False
        ru.bs[c] = 1
        prev = c
        i += 1
    if i >= n:
        return False
    i += 1
    if i >= n or r[i] != ord('S'):
        return False
    i += 1
    prev = -1
    while i < n:
        c = code(r[i])
        if c < 0 or c <= prev:
            return False
        ru.ss[c] = 1
        prev = c
        i += 1
    return True

def parse_num(d: bytes, a: int, b: int, maxlen: int, nolead: bool) -> int:
    if b <= a or b - a > maxlen:
        return -1
    if nolead and d[a] == ord('0'):
        return -1
    v = 0
    for i in range(a, b):
        c = d[i]
        if c < ord('0') or c > ord('9'):
            return -1
        v = v * 10 + (c - ord('0'))
    return v

def main() -> int:
    if len(sys.argv) != 3:
        return 1
    ru = Rule([0] * 13, [0] * 13)
    if not parse_rule(sys.argv[1].encode(), ru):
        return 1
    bs = ru.bs
    ss = ru.ss
    ga = sys.argv[1 + 1].encode()
    k = 0
    while k < len(ga) - 1 and ga[k] == ord('0'):
        k += 1
    gens = parse_num(ga, k, len(ga), 6, False)
    if gens < 0 or gens > 100000:
        return 1
    d = read_stdin_bytes(1 << 40)
    n = len(d)
    nl = d.find(b'\n')
    if nl < 0:
        return 1
    sp = d.find(b' ')
    if sp < 0 or sp > nl:
        return 1
    w = parse_num(d, 0, sp, 4, True)
    h = parse_num(d, sp + 1, nl, 4, True)
    if w < 1 or w > 4096 or h < 1 or (h > 4096):
        return 1
    start = nl + 1
    rest = n - start
    full = h * (w + 1)
    if rest != full and rest != full - 1:
        return 1
    cur = bytearray(w * h)
    for y in range(h):
        base = start + y * (w + 1)
        for x in range(w):
            c = d[base + x]
            if c == ord('o'):
                cur[y * w + x] = 1
            elif c != ord('.'):
                return 1
        if base + w < n and d[base + w] != ord('\n'):
            return 1
    nxt = bytearray(w * h)
    xl = [0] * w
    xr = [0] * w
    for x in range(w):
        xl[x] = (x + w - 1) % w
        xr[x] = (x + 1) % w
    out = bytearray()
    for g in range(1, gens + 1):
        alive = 0
        scars = 0
        for y in range(h):
            up = (y + h - 1) % h * w
            mid = y * w
            dn = (y + 1) % h * w
            for x in range(w):
                a = xl[x]
                b = xr[x]
                wt = 0
                if cur[up + x] == 1:
                    wt += 2
                if cur[dn + x] == 1:
                    wt += 2
                if cur[mid + a] == 1:
                    wt += 2
                if cur[mid + b] == 1:
                    wt += 2
                if cur[up + a] == 1:
                    wt += 1
                if cur[up + b] == 1:
                    wt += 1
                if cur[dn + a] == 1:
                    wt += 1
                if cur[dn + b] == 1:
                    wt += 1
                s = cur[mid + x]
                r = 0
                if s == 1:
                    if ss[wt] == 1:
                        r = 1
                        alive += 1
                    else:
                        r = 2
                        scars += 1
                elif s == 0:
                    if bs[wt] == 1:
                        r = 1
                        alive += 1
                nxt[mid + x] = r
        tmp = cur
        cur = nxt
        nxt = tmp
        out.extend(f'{g} {alive} {scars}\n'.encode())
    for y in range(h):
        for x in range(w):
            s = cur[y * w + x]
            if s == 1:
                out.append(ord('o'))
            elif s == 2:
                out.append(ord('x'))
            else:
                out.append(ord('.'))
        out.append(ord('\n'))
    write_stdout_bytes(out)
    return 0

if __name__ == "__main__":
    sys.exit(main())
