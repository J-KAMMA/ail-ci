import re
import sys

NAME_RE = re.compile(r'[a-z0-9_]{1,16}')
QTY_RE = re.compile(r'-?[0-9]+')
PRICE_RE = re.compile(r'[0-9]+')


def to_int(s):
    neg = s[0] == '-'
    digits = (s[1:] if neg else s).lstrip('0')
    if len(digits) > 18:
        return None  # far outside any allowed range
    v = int(digits) if digits else 0
    return -v if neg else v


def main():
    data = sys.stdin.buffer.read().decode('latin-1')
    if data == '':
        lines = []
    else:
        parts = data.split('\n')
        if parts[-1] == '':
            parts.pop()
        lines = parts[1:]  # first line is the header, dropped unchecked

    good = 0
    bad = 0
    groups = {}  # (region, product) -> [qty_sum, revenue]

    for line in lines:
        f = line.split(',')
        if len(f) != 4:
            bad += 1
            continue
        region, product, qs, ps = f
        if (not NAME_RE.fullmatch(region) or not NAME_RE.fullmatch(product)
                or not QTY_RE.fullmatch(qs) or not PRICE_RE.fullmatch(ps)):
            bad += 1
            continue
        qty = to_int(qs)
        price = to_int(ps)
        if (qty is None or price is None
                or not (-1000 <= qty <= 1000)
                or not (0 <= price <= 10000000)):
            bad += 1
            continue
        good += 1
        key = (region, product)
        g = groups.get(key)
        if g is None:
            groups[key] = [qty, qty * price]
        else:
            g[0] += qty
            g[1] += qty * price

    out = []
    out.append(f"rows {good} bad {bad} groups {len(groups)}")

    top = sorted(groups.items(),
                 key=lambda kv: (-kv[1][1], kv[0][0], kv[0][1]))[:10]
    for (r, p), (q, rev) in top:
        out.append(f"{r} {p} {q} {rev}")

    regions = {}
    for (r, _p), (_q, rev) in groups.items():
        regions[r] = regions.get(r, 0) + rev
    for r in sorted(regions):
        out.append(f"region {r} revenue {regions[r]}")

    total = sum(regions.values())
    out.append(f"total {total}")

    sys.stdout.write("\n".join(out) + "\n")


if __name__ == "__main__":
    main()
