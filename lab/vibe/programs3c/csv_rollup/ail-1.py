import sys


def valid_name(s):
    if len(s) < 1 or len(s) > 16:
        return False
    for ch in s:
        if not (('a' <= ch <= 'z') or ('0' <= ch <= '9') or ch == '_'):
            return False
    return True


def all_digits(s):
    if len(s) == 0:
        return False
    for ch in s:
        if not ('0' <= ch <= '9'):
            return False
    return True


def parse_qty(s):
    neg = False
    if s.startswith('-'):
        neg = True
        s = s[1:]
    if not all_digits(s):
        return None
    d = s.lstrip('0')
    if len(d) > 4:
        return None
    v = int(d) if len(d) > 0 else 0
    if neg:
        v = -v
    if v < -1000 or v > 1000:
        return None
    return v


def parse_price(s):
    if not all_digits(s):
        return None
    d = s.lstrip('0')
    if len(d) > 8:
        return None
    v = int(d) if len(d) > 0 else 0
    if v > 10000000:
        return None
    return v


def main():
    raw = sys.stdin.buffer.read()
    text = raw.decode('latin-1')
    if text == '':
        lines = []
    else:
        lines = text.split('\n')
        if text.endswith('\n'):
            lines.pop()
        lines = lines[1:]

    groups = {}
    regions = {}
    good = 0
    bad = 0
    total = 0

    for line in lines:
        f = line.split(',')
        if len(f) != 4:
            bad += 1
            continue
        r = f[0]
        p = f[1]
        if not valid_name(r) or not valid_name(p):
            bad += 1
            continue
        q = parse_qty(f[2])
        if q is None:
            bad += 1
            continue
        pr = parse_price(f[3])
        if pr is None:
            bad += 1
            continue
        good += 1
        key = (r, p)
        g = groups.get(key)
        if g is None:
            g = [0, 0]
            groups[key] = g
        rev = q * pr
        g[0] += q
        g[1] += rev
        regions[r] = regions.get(r, 0) + rev
        total += rev

    items = []
    for k, v in groups.items():
        items.append((k[0], k[1], v[0], v[1]))
    items.sort(key=lambda t: (-t[3], t[0], t[1]))

    out = []
    out.append("rows " + str(good) + " bad " + str(bad) + " groups " + str(len(groups)))
    top = items[:10]
    for t in top:
        out.append(t[0] + " " + t[1] + " " + str(t[2]) + " " + str(t[3]))
    for rname in sorted(regions.keys()):
        out.append("region " + rname + " revenue " + str(regions[rname]))
    out.append("total " + str(total))

    sys.stdout.write("\n".join(out) + "\n")


main()
