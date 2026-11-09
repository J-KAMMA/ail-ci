import sys


def parse_codes(t):
    vals = []
    prev = -1
    for ch in t:
        if '0' <= ch <= '9':
            v = ord(ch) - 48
        elif ch == 'A':
            v = 10
        elif ch == 'B':
            v = 11
        elif ch == 'C':
            v = 12
        else:
            return None
        if v <= prev:
            return None
        prev = v
        vals.append(v)
    return vals


def parse_dim(p):
    if len(p) == 0 or len(p) > 4 or not p.isdigit() or p[0] == 48:
        return None
    v = int(p.decode())
    if v < 1 or v > 4096:
        return None
    return v


def main():
    args = sys.argv
    if len(args) != 3:
        return 1

    rule = args[1]
    if len(rule) < 3 or rule[0] != 'B':
        return 1
    idx = rule.find('/S')
    if idx < 1:
        return 1
    bl = parse_codes(rule[1:idx])
    sl = parse_codes(rule[idx + 2:])
    if bl is None or sl is None:
        return 1

    gs = args[2]
    if len(gs) == 0:
        return 1
    for ch in gs:
        if not ('0' <= ch <= '9'):
            return 1
    gs2 = gs.lstrip('0')
    if len(gs2) > 6:
        return 1
    G = int(gs2) if gs2 else 0
    if G > 100000:
        return 1

    data = sys.stdin.buffer.read()
    lines = data.split(b'\n')
    parts = lines[0].split(b' ')
    if len(parts) != 2:
        return 1
    W = parse_dim(parts[0])
    H = parse_dim(parts[1])
    if W is None or H is None:
        return 1

    n = len(lines)
    if data.endswith(b'\n'):
        if n != H + 2:
            return 1
    else:
        if n != H + 1:
            return 1

    s = []
    for y in range(H):
        row = lines[1 + y]
        if len(row) != W:
            return 1
        for c in row:
            if c == 46:
                s.append(0)
            elif c == 111:
                s.append(1)
            else:
                return 1

    N = W * H
    birth = [False] * 13
    for v in bl:
        birth[v] = True
    surv = [False] * 13
    for v in sl:
        surv[v] = True

    XM = [(x - 1) % W for x in range(W)]
    XP = [(x + 1) % W for x in range(W)]

    a = [1 if v == 1 else 0 for v in s]
    out = []
    for g in range(1, G + 1):
        ns = [0] * N
        na = [0] * N
        na_cnt = 0
        sc_cnt = 0
        for y in range(H):
            yc = y * W
            ym = ((y - 1) % H) * W
            yp = ((y + 1) % H) * W
            for x in range(W):
                xm = XM[x]
                xp = XP[x]
                w = (2 * (a[ym + x] + a[yp + x] + a[yc + xm] + a[yc + xp])
                     + a[ym + xm] + a[ym + xp] + a[yp + xm] + a[yp + xp])
                i = yc + x
                c = s[i]
                if c == 1:
                    v = 1 if surv[w] else 2
                elif c == 2:
                    v = 0
                else:
                    v = 1 if birth[w] else 0
                ns[i] = v
                if v == 1:
                    na[i] = 1
                    na_cnt += 1
                elif v == 2:
                    sc_cnt += 1
        s = ns
        a = na
        out.append(str(g) + " " + str(na_cnt) + " " + str(sc_cnt) + "\n")

    rows = []
    for y in range(H):
        base = y * W
        rows.append(''.join('.ox'[s[base + x]] for x in range(W)))

    sys.stdout.write(''.join(out) + '\n'.join(rows) + '\n')
    return 0


if __name__ == "__main__":
    code = main()
    if code != 0:
        sys.exit(code)
    sys.exit(0)
