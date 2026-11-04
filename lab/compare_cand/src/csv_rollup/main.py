import sys

NAME = frozenset(b'abcdefghijklmnopqrstuvwxyz0123456789_')


def name_ok(f):
    n = len(f)
    if n < 1 or n > 16:
        return False
    for c in f:
        if c not in NAME:
            return False
    return True


def number(f, allow_neg):
    i = 0
    neg = False
    if allow_neg and f[:1] == b'-':
        neg = True
        i = 1
    if i >= len(f):
        return None
    v = 0
    for c in f[i:]:
        if c < 48 or c > 57:
            return None
        if v <= 10000001:
            v = v * 10 + (c - 48)
    return -v if neg else v


def main():
    data = sys.stdin.buffer.read()
    if not data:
        sys.stdout.write("rows 0 bad 0 groups 0\ntotal 0\n")
        return
    lines = data.split(b"\n")
    if lines and lines[-1] == b"":
        lines.pop()
    groups = {}
    regions = {}
    good = 0
    bad = 0
    for line in lines[1:]:
        f = line.split(b",")
        if len(f) != 4:
            bad += 1
            continue
        reg, prod, qf, pf = f
        if not name_ok(reg) or not name_ok(prod) or not qf or not pf:
            bad += 1
            continue
        qty = number(qf, True)
        price = number(pf, False)
        if qty is None or price is None or qty < -1000 or qty > 1000 or price < 0 or price > 10000000:
            bad += 1
            continue
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
    out = ["rows %d bad %d groups %d" % (good, bad, len(groups))]
    order = sorted(groups.items(), key=lambda kv: (-kv[1][1], kv[0][0], kv[0][1]))
    for (reg, prod), (qty, rev) in order[:10]:
        out.append("%s %s %d %d" % (reg.decode(), prod.decode(), qty, rev))
    for reg in sorted(regions):
        out.append("region %s revenue %d" % (reg.decode(), regions[reg]))
    out.append("total %d" % sum(regions.values()))
    sys.stdout.write("\n".join(out) + "\n")


main()
