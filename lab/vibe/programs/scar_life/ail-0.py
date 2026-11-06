import sys


def main():
    args = sys.argv[1:]
    if len(args) != 2:
        sys.exit(1)

    rule = args[0]
    gens_s = args[1]

    if not rule.startswith('B'):
        sys.exit(1)
    parts = rule.split('/')
    if len(parts) != 2:
        sys.exit(1)
    p0, p1 = parts
    if not p0.startswith('B'):
        sys.exit(1)
    if not p1.startswith('S'):
        sys.exit(1)
    bpart = p0[1:]
    spart = p1[1:]

    valid = "0123456789ABC"

    def parse_codes(s):
        prev = -1
        out = []
        for ch in s:
            idx = valid.find(ch)
            if idx < 0:
                sys.exit(1)
            if idx <= prev:
                sys.exit(1)
            prev = idx
            out.append(idx)
        return out

    Blist = parse_codes(bpart)
    Slist = parse_codes(spart)

    Bb = [False] * 13
    Sb = [False] * 13
    for v in Blist:
        Bb[v] = True
    for v in Slist:
        Sb[v] = True

    if not gens_s:
        sys.exit(1)
    for ch in gens_s:
        if ch < '0' or ch > '9':
            sys.exit(1)
    t = gens_s.lstrip('0')
    if t == '':
        gens = 0
    else:
        if len(t) > 6:
            sys.exit(1)
        gens = int(t)
        if gens > 100000:
            sys.exit(1)

    raw = sys.stdin.buffer.read()
    try:
        text = raw.decode('ascii')
    except UnicodeDecodeError:
        sys.exit(1)

    nl = text.find('\n')
    if nl < 0:
        sys.exit(1)
    header = text[:nl]
    rest = text[nl + 1:]

    hp = header.split(' ')
    if len(hp) != 2:
        sys.exit(1)
    dims = []
    for h in hp:
        if not h or len(h) > 4:
            sys.exit(1)
        for ch in h:
            if ch < '0' or ch > '9':
                sys.exit(1)
        if h[0] == '0':
            sys.exit(1)
        v = int(h)
        if v < 1 or v > 4096:
            sys.exit(1)
        dims.append(v)
    W, H = dims

    need = H * (W + 1)
    L = len(rest)
    if L == need:
        final_nl = True
    elif L == need - 1:
        final_nl = False
    else:
        sys.exit(1)

    grid = []
    pos = 0
    for i in range(H):
        line = rest[pos:pos + W]
        row = bytearray(W)
        for x in range(W):
            ch = line[x]
            if ch == '.':
                row[x] = 0
            elif ch == 'o':
                row[x] = 1
            else:
                sys.exit(1)
        grid.append(row)
        pos += W
        if i < H - 1 or final_nl:
            if rest[pos] != '\n':
                sys.exit(1)
            pos += 1

    masks = []
    for row in grid:
        m = bytearray(W)
        for x in range(W):
            if row[x] == 1:
                m[x] = 1
        masks.append(m)

    w = W
    h = H
    xls = [w - 1] + list(range(0, w - 1))
    xrs = list(range(1, w)) + [0]

    out = []

    for g in range(1, gens + 1):
        newgrid = [bytearray(w) for _ in range(h)]
        newmasks = [bytearray(w) for _ in range(h)]
        alive = 0
        scar = 0
        for y in range(h):
            curm = masks[y]
            curg = grid[y]
            if h == 1:
                prevm = curm
                nextm = curm
            else:
                prevm = masks[y - 1]
                nextm = masks[(y + 1) % h]
            newrow = newgrid[y]
            newmask = newmasks[y]
            for x in range(w):
                xl = xls[x]
                xr = xrs[x]
                wt = 2 * (prevm[x] + nextm[x] + curm[xl] + curm[xr]) \
                    + prevm[xl] + prevm[xr] + nextm[xl] + nextm[xr]
                st = curg[x]
                if st == 1:
                    if Sb[wt]:
                        newrow[x] = 1
                        newmask[x] = 1
                        alive += 1
                    else:
                        newrow[x] = 2
                        scar += 1
                elif st == 0:
                    if Bb[wt]:
                        newrow[x] = 1
                        newmask[x] = 1
                        alive += 1
        grid = newgrid
        masks = newmasks
        out.append("%d %d %d" % (g, alive, scar))

    table = bytes.maketrans(b'\x00\x01\x02', b'.ox')
    for row in grid:
        out.append(bytes(row).translate(table).decode('ascii'))

    sys.stdout.write('\n'.join(out) + '\n')


main()
