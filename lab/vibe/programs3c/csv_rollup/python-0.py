import re
import sys

NAME_RE = re.compile(rb'[a-z0-9_]{1,16}')
INT_RE = re.compile(rb'-?[0-9]+')
UINT_RE = re.compile(rb'[0-9]+')


def parse_qty(b):
    if not INT_RE.fullmatch(b):
        return None
    neg = b[:1] == b'-'
    d = b[1:] if neg else b
    d = d.lstrip(b'0')
    if len(d) > 12:
        return None
    v = int(d.decode()) if d else 0
    if neg:
        v = -v
    if -1000 <= v <= 1000:
        return v
    return None


def parse_price(b):
    if not UINT_RE.fullmatch(b):
        return None
    d = b.lstrip(b'0')
    if len(d) > 12:
        return None
    v = int(d.decode()) if d else 0
    if 0 <= v <= 10000000:
        return v
    return None


def main():
    data = sys.stdin.buffer.read()
    out = []

    if not data:
        out.append("rows 0 bad 0 groups 0\n")
        out.append("total 0\n")
        sys.stdout.write("".join(out))
        return

    lines = data.split(b'\n')
    if data.endswith(b'\n'):
        lines.pop()
    lines = lines[1:]  # drop header unchecked

    good = 0
    bad = 0
    groups = {}

    for line in lines:
        f = line.split(b',')
        if len(f) != 4:
            bad += 1
            continue
        region, product, qb, pb = f
        if not NAME_RE.fullmatch(region) or not NAME_RE.fullmatch(product):
            bad += 1
            continue
        q = parse_qty(qb)
        p = parse_price(pb)
        if q is None or p is None:
            bad += 1
            continue
        good += 1
        key = (region, product)
        g = groups.get(key)
        if g is None:
            groups[key] = [q, q * p]
        else:
            g[0] += q
            g[1] += q * p

    out.append(f"rows {good} bad {bad} groups {len(groups)}\n")

    ranked = sorted(groups.items(), key=lambda kv: (-kv[1][1], kv[0][0], kv[0][1]))
    for (r, p), (qs, rev) in ranked[:10]:
        out.append(f"{r.decode()} {p.decode()} {qs} {rev}\n")

    region_rev = {}
    for (r, _p), (_qs, rev) in groups.items():
        region_rev[r] = region_rev.get(r, 0) + rev

    for r in sorted(region_rev):
        out.append(f"region {r.decode()} revenue {region_rev[r]}\n")

    total = sum(rev for (_qs, rev) in groups.values())
    out.append(f"total {total}\n")

    sys.stdout.write("".join(out))


if __name__ == "__main__":
    main()
