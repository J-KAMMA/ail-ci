import sys
import re

RP_RE = re.compile(rb'[a-z0-9_]{1,16}')
QTY_RE = re.compile(rb'-?[0-9]+')
PRICE_RE = re.compile(rb'[0-9]+')


def main():
    data = sys.stdin.buffer.read()
    lines = data.split(b'\n')
    if lines and lines[-1] == b'':
        lines.pop()
    data_lines = lines[1:]

    groups = {}
    good = 0
    bad = 0

    for line in data_lines:
        fields = line.split(b',')
        if len(fields) != 4:
            bad += 1
            continue

        region, product, qty_s, price_s = fields

        if not (RP_RE.fullmatch(region) and RP_RE.fullmatch(product)):
            bad += 1
            continue
        if not (QTY_RE.fullmatch(qty_s) and PRICE_RE.fullmatch(price_s)):
            bad += 1
            continue

        try:
            qty = int(qty_s)
            price = int(price_s)
        except ValueError:
            bad += 1
            continue

        if qty < -1000 or qty > 1000 or price < 0 or price > 10000000:
            bad += 1
            continue

        good += 1
        key = (region, product)
        entry = groups.get(key)
        if entry is None:
            groups[key] = [qty, qty * price]
        else:
            entry[0] += qty
            entry[1] += qty * price

    ranked = sorted(
        groups.items(),
        key=lambda item: (-item[1][1], item[0][0], item[0][1]),
    )
    top = ranked[:10]

    region_totals = {}
    total = 0
    for (region, _product), (_qsum, revenue) in groups.items():
        region_totals[region] = region_totals.get(region, 0) + revenue
        total += revenue

    out = [b"rows %d bad %d groups %d" % (good, bad, len(groups))]

    for (region, product), (qsum, revenue) in top:
        out.append(b"%s %s %d %d" % (region, product, qsum, revenue))

    for region in sorted(region_totals):
        out.append(b"region %s revenue %d" % (region, region_totals[region]))

    out.append(b"total %d" % total)

    sys.stdout.buffer.write(b"\n".join(out) + b"\n")


main()
