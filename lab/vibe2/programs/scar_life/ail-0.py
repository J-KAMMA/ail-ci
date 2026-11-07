import sys
import re


def main():
    if len(sys.argv) != 3:
        sys.exit(1)

    rule = sys.argv[1]
    gens_s = sys.argv[2]

    m = re.fullmatch(r'B([0-9ABC]*)/S([0-9ABC]*)', rule)
    if m is None:
        sys.exit(1)

    def conv(s):
        vals = []
        prev = -1
        for ch in s:
            if '0' <= ch <= '9':
                v = ord(ch) - 48
            else:
                v = ord(ch) - 55
            if v <= prev:
                return None
            prev = v
            vals.append(v)
        return set(vals)

    born = conv(m.group(1))
    if born is None:
        sys.exit(1)
    stays = conv(m.group(2))
    if stays is None:
        sys.exit(1)

    if re.fullmatch(r'[0-9]+', gens_s) is None:
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

    data = sys.stdin.read()

    nl = data.find('\n')
    if nl < 0:
        sys.exit(1)
    header = data[:nl]
    rest = data[nl + 1:]

    hm = re.fullmatch(r'([1-9][0-9]*) ([1-9][0-9]*)', header)
    if hm is None:
        sys.exit(1)
    W = int(hm.group(1))
    H = int(hm.group(2))
    if W > 4096 or H > 4096:
        sys.exit(1)

    if rest == '':
        sys.exit(1)
    if rest[-1] == '\n':
        trimmed = rest[:-1]
    else:
        trimmed = rest

    lines = trimmed.split('\n')
    if len(lines) != H:
        sys.exit(1)
    for ln in lines:
        if len(ln) != W:
            sys.exit(1)
        for ch in ln:
            if ch != '.' and ch != 'o':
                sys.exit(1)

    bmask = [False] * 13
    for v in born:
        bmask[v] = True
    smask = [False] * 13
    for v in stays:
        smask[v] = True

    rows = []
    for ln in lines:
        row = [0] * (W + 2)
        for j in range(W):
            if ln[j] == 'o':
                row[j + 1] = 1
        row[0] = row[W]
        row[W + 1] = row[1]
        rows.append(row)

    out = []

    for g in range(1, gens + 1):
        new_rows = []
        alive_total = 0
        scar_total = 0
        for r in range(H):
            up = rows[(r - 1) % H]
            cur = rows[r]
            dn = rows[(r + 1) % H]

            u0 = up[1:W + 1]
            ul = up[0:W]
            ur = up[2:W + 2]
            d0 = dn[1:W + 1]
            dl = dn[0:W]
            dr = dn[2:W + 2]
            cl = cur[0:W]
            cr = cur[2:W + 2]
            cc = cur[1:W + 1]

            inner = []
            app = inner.append
            for uo, ulv, urv, do, dlv, drv, clv, crv, ccv in zip(
                    u0, ul, ur, d0, dl, dr, cl, cr, cc):
                w = 2 * ((uo == 1) + (do == 1) + (clv == 1) + (crv == 1)) \
                    + ((ulv == 1) + (urv == 1) + (dlv == 1) + (drv == 1))
                if ccv == 1:
                    if smask[w]:
                        app(1)
                        alive_total += 1
                    else:
                        app(2)
                        scar_total += 1
                elif ccv == 0:
                    if bmask[w]:
                        app(1)
                        alive_total += 1
                    else:
                        app(0)
                else:
                    app(0)

            padded = [0] * (W + 2)
            padded[0] = inner[W - 1]
            padded[1:W + 1] = inner
            padded[W + 1] = inner[0]
            new_rows.append(padded)

        rows = new_rows
        out.append(str(g) + ' ' + str(alive_total) + ' ' + str(scar_total))

    for row in rows:
        chars = []
        for j in range(1, W + 1):
            v = row[j]
            if v == 0:
                chars.append('.')
            elif v == 1:
                chars.append('o')
            else:
                chars.append('x')
        out.append(''.join(chars))

    sys.stdout.write('\n'.join(out) + '\n')


main()
