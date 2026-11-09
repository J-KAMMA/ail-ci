import sys
import re


def parse_codes(s):
    prev = -1
    out = set()
    for ch in s:
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
        out.add(v)
    return out


def parse_rule(rule):
    if not rule.startswith('B'):
        return None
    rest = rule[1:]
    if rest.count('/') != 1:
        return None
    bpart, spart = rest.split('/')
    if not spart.startswith('S'):
        return None
    b = parse_codes(bpart)
    s = parse_codes(spart[1:])
    if b is None or s is None:
        return None
    return b, s


def parse_gens(s):
    if not s:
        return None
    for ch in s:
        if ch < '0' or ch > '9':
            return None
    t = s.lstrip('0')
    if t == '':
        return 0
    if len(t) > 6:
        return None
    v = int(t)
    if v > 100000:
        return None
    return v


def main():
    if len(sys.argv) != 3:
        sys.exit(1)

    parsed_rule = parse_rule(sys.argv[1])
    if parsed_rule is None:
        sys.exit(1)
    B, S = parsed_rule

    gens = parse_gens(sys.argv[2])
    if gens is None:
        sys.exit(1)

    data = sys.stdin.buffer.read()
    if not data.isascii():
        sys.exit(1)

    nl = data.find(b'\n')
    if nl < 0:
        sys.exit(1)
    header = data[:nl]
    if re.fullmatch(rb'[1-9][0-9]* [1-9][0-9]*', header) is None:
        sys.exit(1)
    ws, hs = header.split(b' ')
    if len(ws) > 4 or len(hs) > 4:
        sys.exit(1)
    W = int(ws)
    H = int(hs)
    if W > 4096 or H > 4096:
        sys.exit(1)

    body = data[nl + 1:]
    parts = body.split(b'\n')
    if parts and parts[-1] == b'':
        parts.pop()
    if len(parts) != H:
        sys.exit(1)

    tbl = bytes.maketrans(b'.o', b'\x00\x01')
    grid = []
    for part in parts:
        if len(part) != W:
            sys.exit(1)
        if part.count(b'.') + part.count(b'o') != W:
            sys.exit(1)
        grid.append(bytearray(part.translate(tbl)))

    lookup = bytearray(39)
    for w in range(13):
        lookup[w] = 1 if w in B else 0
        lookup[13 + w] = 1 if w in S else 2
        lookup[26 + w] = 0

    dead_tbl = bytes.maketrans(b'\x00\x01\x02', b'\x00\x01\x00')
    chars = '.ox'
    out = []

    for gen in range(1, gens + 1):
        amask = [row.translate(dead_tbl) for row in grid]
        ls = [m[-1:] + m[:-1] for m in amask]
        rs = [m[1:] + m[:1] for m in amask]

        new = []
        alive = 0
        scars = 0
        for i in range(H):
            im = i - 1 if i > 0 else H - 1
            ip = i + 1 if i + 1 < H else 0

            up = amask[im]
            down = amask[ip]
            left = ls[i]
            right = rs[i]
            ul = ls[im]
            ur = rs[im]
            dl = ls[ip]
            dr = rs[ip]

            weights = [2 * (a + b + c + d) + (e + f + g + h)
                       for a, b, c, d, e, f, g, h in
                       zip(up, down, left, right, ul, ur, dl, dr)]

            cur = grid[i]
            nr = bytearray(lookup[c * 13 + w]
                           for c, w in zip(cur, weights))
            alive += nr.count(1)
            scars += nr.count(2)
            new.append(nr)

        grid = new
        out.append(str(gen) + ' ' + str(alive) + ' ' + str(scars))

    for row in grid:
        out.append(''.join(chars[v] for v in row))

    sys.stdout.write('\n'.join(out) + '\n')


if __name__ == '__main__':
    main()
