import sys

ALLOWED = set(b"abcdefghijklmnopqrstuvwxyz0123456789_")


def is_name(s):
    n = len(s)
    if n < 1 or n > 16:
        return False
    for c in s:
        if c not in ALLOWED:
            return False
    return True


def parse_qty(s):
    n = len(s)
    if n == 0:
        return None

    i = 0
    neg = False
    if s[0] == 45:
        neg = True
        i = 1
        if i == n:
            return None

    j = i
    while j < n:
        c = s[j]
        if c < 48 or c > 57:
            return None
        j += 1

    j = i
    while j < n and s[j] == 48:
        j += 1

    if j == n:
        v = 0
    else:
        if n - j > 4:
            return None
        v = 0
        while j < n:
            v = v * 10 + (s[j] - 48)
            j += 1

    if neg:
        v = -v

    if v < -1000 or v > 1000:
        return None
    return v


def parse_price(s):
    n = len(s)
    if n == 0:
        return None

    j = 0
    while j < n:
        c = s[j]
        if c < 48 or c > 57:
            return None
        j += 1

    j = 0
    while j < n and s[j] == 48:
        j += 1

    if j == n:
        return 0

    if n - j > 8:
        return None

    v = 0
    while j < n:
        v = v * 10 + (s[j] - 48)
        j += 1

    if v > 10000000:
        return None
    return v


def group_key(item):
    key = item[0]
    value = item[1]
    return (-value[1], key[0], key[1])


def num(n):
    return str(n).encode()


def main():
    data = sys.stdin.buffer.read()
    lines = data.split(b"\n")

    if data and data[-1] == 10:
        lines = lines[:-1]

    groups = {}
    good = 0
    bad = 0

    for line in lines[1:]:
        parts = line.split(b",")
        if len(parts) != 4:
            bad += 1
            continue

        region = parts[0]
        product = parts[1]
        qty_s = parts[2]
        price_s = parts[3]

        if not is_name(region) or not is_name(product):
            bad += 1
            continue

        qty = parse_qty(qty_s)
        if qty is None:
            bad += 1
            continue

        price = parse_price(price_s)
        if price is None:
            bad += 1
            continue

        good += 1
        key = (region, product)

        if key in groups:
            g = groups[key]
            g[0] = g[0] + qty
            g[1] = g[1] + qty * price
        else:
            groups[key] = [qty, qty * price]

    ordered = sorted(groups.items(), key=group_key)

    out = []
    out.append(
        b"rows " + num(good) + b" bad " + num(bad) +
        b" groups " + num(len(groups))
    )

    limit = len(ordered)
    if limit > 10:
        limit = 10

    i = 0
    while i < limit:
        key = ordered[i][0]
        value = ordered[i][1]
        out.append(
            key[0] + b" " + key[1] + b" " +
            num(value[0]) + b" " + num(value[1])
        )
        i += 1

    region_sums = {}
    for key in groups:
        value = groups[key]
        region = key[0]
        if region in region_sums:
            region_sums[region] = region_sums[region] + value[1]
        else:
            region_sums[region] = value[1]

    regions = sorted(region_sums)
    for region in regions:
        out.append(
            b"region " + region + b" revenue " + num(region_sums[region])
        )

    total = 0
    for key in groups:
        total = total + groups[key][1]

    out.append(b"total " + num(total))

    sys.stdout.buffer.write(b"\n".join(out) + b"\n")


main()
