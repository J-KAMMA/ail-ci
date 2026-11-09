import sys


def valid_name(f):
    n = len(f)
    if n < 1 or n > 16:
        return False
    for c in f:
        if c >= 97 and c <= 122:
            continue
        if c >= 48 and c <= 57:
            continue
        if c == 95:
            continue
        return False
    return True


def parse_qty(f):
    n = len(f)
    if n == 0:
        return None
    i = 0
    neg = False
    if f[0] == 45:
        neg = True
        i = 1
        if i == n:
            return None
    val = 0
    while i < n:
        c = f[i]
        if c < 48 or c > 57:
            return None
        val = val * 10 + (c - 48)
        if val > 1000:
            return None
        i += 1
    if neg:
        return -val
    return val


def parse_price(f):
    n = len(f)
    if n == 0:
        return None
    val = 0
    i = 0
    while i < n:
        c = f[i]
        if c < 48 or c > 57:
            return None
        val = val * 10 + (c - 48)
        if val > 10000000:
            return None
        i += 1
    return val


def main():
    data = sys.stdin.buffer.read()
    if len(data) == 0:
        sys.stdout.buffer.write(b"rows 0 bad 0 groups 0\ntotal 0\n")
        return

    lines = data.split(b"\n")
    data_lines = lines[1:]
    if data[-1] == 10 and len(data_lines) > 0:
        data_lines = data_lines[:-1]

    groups = {}
    region_totals = {}
    good = 0
    bad = 0

    for line in data_lines:
        parts = line.split(b",")
        if len(parts) != 4:
            bad += 1
            continue

        region = parts[0]
        product = parts[1]
        qty_field = parts[2]
        price_field = parts[3]

        if not valid_name(region) or not valid_name(product):
            bad += 1
            continue

        qty = parse_qty(qty_field)
        if qty is None:
            bad += 1
            continue

        price = parse_price(price_field)
        if price is None:
            bad += 1
            continue

        good += 1
        key = (region, product)
        if key in groups:
            old = groups[key]
            groups[key] = (old[0] + qty, old[1] + qty * price)
        else:
            groups[key] = (qty, qty * price)

    group_list = []
    total = 0

    for key in groups:
        qsum, revenue = groups[key]
        region = key[0]
        product = key[1]
        group_list.append((region, product, qsum, revenue))
        if region in region_totals:
            region_totals[region] = region_totals[region] + revenue
        else:
            region_totals[region] = revenue
        total += revenue

    group_list.sort(key=lambda g: (g[0], g[1]))
    group_list.sort(key=lambda g: g[3], reverse=True)

    out = []
    out.append(b"rows " + str(good).encode() + b" bad " + str(bad).encode() + b" groups " + str(len(groups)).encode() + b"\n")

    count = len(group_list)
    if count > 10:
        count = 10
    i = 0
    while i < count:
        g = group_list[i]
        out.append(g[0] + b" " + g[1] + b" " + str(g[2]).encode() + b" " + str(g[3]).encode() + b"\n")
        i += 1

    regions = sorted(region_totals.keys())
    for region in regions:
        out.append(b"region " + region + b" revenue " + str(region_totals[region]).encode() + b"\n")

    out.append(b"total " + str(total).encode() + b"\n")
    sys.stdout.buffer.write(b"".join(out))


if __name__ == "__main__":
    main()
