import sys

NAME_CHARS = frozenset(b"abcdefghijklmnopqrstuvwxyz0123456789_")


def valid_name(field):
    if len(field) < 1 or len(field) > 16:
        return False
    for c in field:
        if c not in NAME_CHARS:
            return False
    return True


def parse_qty(field):
    if not field:
        return None

    negative = field[0] == 45
    if negative:
        field = field[1:]

    if not field.isdigit():
        return None

    digits = field.lstrip(b"0")
    if len(digits) > 4:
        return None

    value = int(digits) if digits else 0
    if negative:
        value = -value

    if value < -1000 or value > 1000:
        return None
    return value


def parse_price(field):
    if not field.isdigit():
        return None

    digits = field.lstrip(b"0")
    if len(digits) > 8:
        return None

    value = int(digits) if digits else 0
    if value > 10000000:
        return None
    return value


def main():
    inp = sys.stdin.buffer
    header = inp.readline()

    groups = {}
    region_totals = {}
    good = 0
    bad = 0

    if header != b"":
        for line in inp:
            if line.endswith(b"\n"):
                line = line[:-1]

            fields = line.split(b",")
            if len(fields) != 4:
                bad += 1
                continue

            region, product, qty_field, price_field = fields

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
            revenue = qty * price
            key = (region, product)

            group = groups.get(key)
            if group is None:
                groups[key] = [qty, revenue]
                region_totals[region] = region_totals.get(region, 0) + revenue
            else:
                group[0] += qty
                group[1] += revenue
                region_totals[region] += revenue

    top = sorted(
        groups.items(),
        key=lambda item: (-item[1][1], item[0][0], item[0][1]),
    )[:10]

    out = [
        b"rows "
        + str(good).encode()
        + b" bad "
        + str(bad).encode()
        + b" groups "
        + str(len(groups)).encode()
    ]

    for (region, product), (qty_sum, revenue) in top:
        out.append(
            b" ".join(
                (region, product, str(qty_sum).encode(), str(revenue).encode())
            )
        )

    for region in sorted(region_totals):
        out.append(
            b"region "
            + region
            + b" revenue "
            + str(region_totals[region]).encode()
        )

    out.append(b"total " + str(sum(region_totals.values())).encode())

    sys.stdout.buffer.write(b"\n".join(out) + b"\n")


if __name__ == "__main__":
    main()
