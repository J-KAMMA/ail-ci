import sys


def name_ok(data, a, b):
    n = b - a
    if n < 1 or n > 16:
        return False
    i = a
    while i < b:
        c = data[i]
        if c >= 97 and c <= 122:
            i += 1
        elif c >= 48 and c <= 57:
            i += 1
        elif c == 95:
            i += 1
        else:
            return False
    return True


def number(data, a, b, allow_neg):
    i = a
    neg = False
    if allow_neg and i < b and data[i] == 45:
        neg = True
        i += 1
    if i >= b:
        return None
    v = 0
    while i < b:
        c = data[i]
        if c < 48 or c > 57:
            return None
        if v <= 10000001:
            v = v * 10 + (c - 48)
        i += 1
    return -v if neg else v


def main():
    data = sys.stdin.buffer.read()
    n = len(data)
    if n == 0:
        sys.stdout.write("rows 0 bad 0 groups 0\ntotal 0\n")
        return
    pos = 0
    while pos < n and data[pos] != 10:
        pos += 1
    if pos < n:
        pos += 1
    groups = {}
    regions = {}
    good = 0
    bad = 0
    while pos < n:
        e = pos
        while e < n and data[e] != 10:
            e += 1
        c1 = pos
        while c1 < e and data[c1] != 44:
            c1 += 1
        c2 = c1 + 1
        while c2 < e and data[c2] != 44:
            c2 += 1
        c3 = c2 + 1
        while c3 < e and data[c3] != 44:
            c3 += 1
        ok = c1 < e and c2 < e and c3 < e
        if ok:
            c4 = c3 + 1
            while c4 < e and data[c4] != 44:
                c4 += 1
            if c4 < e:
                ok = False
        if ok:
            reg = data[pos:c1]
            prod = data[c1 + 1:c2]
            if not name_ok(data, pos, c1) or not name_ok(data, c1 + 1, c2) or c2 + 1 >= c3 or c3 + 1 >= e:
                ok = False
            else:
                qty = number(data, c2 + 1, c3, True)
                price = number(data, c3 + 1, e, False)
                if qty is None or price is None or qty < -1000 or qty > 1000 or price < 0 or price > 10000000:
                    ok = False
                else:
                    rev = qty * price
                    key = (reg, prod)
                    g = groups.get(key)
                    if g is None:
                        groups[key] = [qty, rev]
                    else:
                        g[0] += qty
                        g[1] += rev
                    regions[reg] = regions.get(reg, 0) + rev
                    good += 1
        if not ok:
            bad += 1
        pos = e + 1
    out = ["rows %d bad %d groups %d" % (good, bad, len(groups))]
    order = sorted(groups.items(), key=lambda kv: (-kv[1][1], kv[0][0], kv[0][1]))
    for (reg, prod), (qty, rev) in order[:10]:
        out.append("%s %s %d %d" % (reg.decode(), prod.decode(), qty, rev))
    for reg in sorted(regions):
        out.append("region %s revenue %d" % (reg.decode(), regions[reg]))
    out.append("total %d" % sum(regions.values()))
    sys.stdout.write("\n".join(out) + "\n")


main()
