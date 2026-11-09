import sys

ALLOWED = "abcdefghijklmnopqrstuvwxyz0123456789_"


def parse_num(s, signed):
    neg = False
    if signed and s[:1] == '-':
        neg = True
        s = s[1:]
    if s == '':
        return None
    v = 0
    for c in s:
        if c < '0' or c > '9':
            return None
        v = v * 10 + (ord(c) - 48)
        if v > 1000000000000:
            return None
    if neg:
        return -v
    return v


def valid_name(s):
    if len(s) < 1 or len(s) > 16:
        return False
    for c in s:
        if c not in ALLOWED:
            return False
    return True


def main():
    raw = sys.stdin.buffer.read().decode('latin-1')
    idx = raw.find('\n')
    if raw == '' or idx < 0:
        data = ''
    else:
        data = raw[idx + 1:]

    lines = []
    if data != '':
        lines = data.split('\n')
        if lines[-1] == '':
            lines.pop()

    good = 0
    bad = 0
    groups = {}

    for line in lines:
        f = line.split(',')
        if len(f) != 4:
            bad += 1
            continue
        region = f[0]
        product = f[1]
        qs = f[2]
        ps = f[3]
        if not valid_name(region) or not valid_name(product):
            bad += 1
            continue
        q = parse_num(qs, True)
        if q is None or q < -1000 or q > 1000:
            bad += 1
            continue
        p = parse_num(ps, False)
        if p is None or p > 10000000:
            bad += 1
            continue
        good += 1
        key = (region, product)
        g = groups.get(key)
        if g is None:
            g = [0, 0]
            groups[key] = g
        g[0] += q
        g[1] += q * p

    out = []
    out.append("rows " + str(good) + " bad " + str(bad) + " groups " + str(len(groups)) + "\n")

    ranked = sorted(groups.items(), key=lambda kv: (-kv[1][1], kv[0][0], kv[0][1]))
    for item in ranked[:10]:
        r = item[0][0]
        p = item[0][1]
        g = item[1]
        out.append(r + " " + p + " " + str(g[0]) + " " + str(g[1]) + "\n")

    regions = {}
    total = 0
    for key, g in groups.items():
        r = key[0]
        regions[r] = regions.get(r, 0) + g[1]
        total += g[1]

    for r in sorted(regions.keys()):
        out.append("region " + r + " revenue " + str(regions[r]) + "\n")

    out.append("total " + str(total) + "\n")
    sys.stdout.write(''.join(out))


main()
