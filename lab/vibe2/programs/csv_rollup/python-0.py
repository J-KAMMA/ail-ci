import sys


def valid_name(s):
    n = len(s)
    if n < 1 or n > 16:
        return False
    for c in s:
        if not (48 <= c <= 57 or 97 <= c <= 122 or c == 95):
            return False
    return True


def parse_qty(s):
    if not s:
        return None

    if s[0] == 45:
        if len(s) == 1:
            return None
        digits = s[1:]
        neg = True
    else:
        digits = s
        neg = False

    if not digits.isdigit():
        return None

    t = digits.lstrip(b"0")
    if not t:
        return 0
    if len(t) > 4:
        return None

    v = int(t)
    if v > 1000:
        return None
    return -v if neg else v


def parse_price(s):
    if not s or not s.isdigit():
        return None

    t = s.lstrip(b"0")
    if not t:
        return 0
    if len(t) > 8:
        return None
    if len(t) == 8 and t > b"10000000":
        return None
    return int(t)


def main():
    data = sys.stdin.buffer.read()
    lines = data.split(b"\n")
    if lines and lines[-1] == b"":
        lines.pop()

    groups = {}
    region_rev = {}
    good = 0
    bad = 0

    for line in lines[1:]:
        parts = line.split(b",")
        if len(parts) != 4:
            bad += 1
            continue

        region, product, qty_s, price_s = parts

        if not valid_name(region) or not valid_name(product):
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
        revenue = qty * price
        key = (region, product)
        entry = groups.get(key)
        if entry is None:
            groups[key] = [qty, revenue]
        else:
            entry[0] += qty
            entry[1] += revenue

        region_rev[region] = region_rev.get(region, 0) + revenue

    out = []
    out.append(f"rows {good} bad {bad} groups {len(groups)}\n".encode())

    top = sorted(
        groups.items(),
        key=lambda kv: (-kv[1][1], kv[0][0], kv[0][1]),
    )[:10]

    for (region, product), (qty_sum, revenue) in top:
        out.append(
            region
            + b" "
            + product
            + b" "
            + str(qty_sum).encode()
            + b" "
            + str(revenue).encode()
            + b"\n"
        )

    for region in sorted(region_rev):
        out.append(
            b"region "
            + region
            + b" revenue "
            + str(region_rev[region]).encode()
            + b"\n"
        )

    out.append(b"total " + str(sum(region_rev.values())).encode() + b"\n")
    sys.stdout.buffer.write(b"".join(out))


if __name__ == "__main__":
    main()
