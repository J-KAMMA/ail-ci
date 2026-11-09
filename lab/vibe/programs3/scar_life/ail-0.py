import sys


def parse_rule(s):
    if len(s) < 2 or s[0] != 'B':
        return None
    idx = s.find('/')
    if idx < 0:
        return None
    if idx + 1 >= len(s) or s[idx + 1] != 'S':
        return None
    bpart = s[1:idx]
    spart = s[idx + 2:]

    def codes(part):
        vals = set()
        prev = -1
        for ch in part:
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
            vals.add(v)
        return vals

    b = codes(bpart)
    sp = codes(spart)
    if b is None or sp is None:
        return None
    return b, sp


def main():
    argv = sys.argv
    if len(argv) != 3:
        sys.exit(1)

    parsed = parse_rule(argv[1])
    if parsed is None:
        sys.exit(1)
    bset, sset = parsed

    gs = argv[2]
    if len(gs) == 0:
        sys.exit(1)
    for ch in gs:
        if ch < '0' or ch > '9':
            sys.exit(1)
    trimmed = gs.lstrip('0')
    if trimmed == '':
        gens = 0
    else:
        if len(trimmed) > 6:
            sys.exit(1)
        gens = int(trimmed)
        if gens > 100000:
            sys.exit(1)

    data = sys.stdin.read()
    lines = data.split('\n')
    if data.endswith('\n'):
        lines.pop()
    if len(lines) < 1:
        sys.exit(1)

    header = lines[0]
    parts = header.split(' ')
    if len(parts) != 2:
        sys.exit(1)
    dims = []
    for p in parts:
        if len(p) == 0 or len(p) > 4:
            sys.exit(1)
        if p[0] == '0':
            sys.exit(1)
        for ch in p:
            if ch < '0' or ch > '9':
                sys.exit(1)
        v = int(p)
        if v < 1 or v > 4096:
            sys.exit(1)
        dims.append(v)
    W, H = dims

    if len(lines) != 1 + H:
        sys.exit(1)

    grid = []
    for r in range(H):
        line = lines[1 + r]
        if len(line) != W:
            sys.exit(1)
        for ch in line:
            if ch == 'o':
                grid.append(1)
            elif ch == '.':
                grid.append(0)
            else:
                sys.exit(1)

    up = [(r - 1) % H for r in range(H)]
    down = [(r + 1) % H for r in range(H)]
    left = [(c - 1) % W for c in range(W)]
    right = [(c + 1) % W for c in range(W)]

    N = W * H
    out = []

    for g in range(1, gens + 1):
        new = [0] * N
        alive = 0
        scar = 0
        for r in range(H):
            ru = up[r] * W
            rd = down[r] * W
            rc = r * W
            for c in range(W):
                cl = left[c]
                cr = right[c]
                w = 0
                if grid[ru + c] == 1:
                    w += 2
                if grid[rd + c] == 1:
                    w += 2
                if grid[rc + cl] == 1:
                    w += 2
                if grid[rc + cr] == 1:
                    w += 2
                if grid[ru + cl] == 1:
                    w += 1
                if grid[ru + cr] == 1:
                    w += 1
                if grid[rd + cl] == 1:
                    w += 1
                if grid[rd + cr] == 1:
                    w += 1
                cur = grid[rc + c]
                if cur == 1:
                    if w in sset:
                        nv = 1
                        alive += 1
                    else:
                        nv = 2
                        scar += 1
                elif cur == 0:
                    if w in bset:
                        nv = 1
                        alive += 1
                    else:
                        nv = 0
                else:
                    nv = 0
                new[rc + c] = nv
        grid = new
        out.append(str(g) + ' ' + str(alive) + ' ' + str(scar))

    for r in range(H):
        base = r * W
        chars = []
        for c in range(W):
            v = grid[base + c]
            if v == 1:
                chars.append('o')
            elif v == 2:
                chars.append('x')
            else:
                chars.append('.')
        out.append(''.join(chars))

    sys.stdout.write('\n'.join(out) + '\n')


main()
