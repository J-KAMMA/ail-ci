import sys
import re

NAME_RE = re.compile(rb'[a-z0-9_]{1,16}')


def parse_qty(field):
    if not field:
        return None

    if field[0] == 45:
        if len(field) == 1:
            return None
        digits = field[1:]
        negative = True
    else:
        digits = field
        negative = False

    if not digits.isdigit():
        return None

    significant = digits.lstrip(b'0')
    if not significant:
        return 0

    if len(significant) > 4:
        return None

    value = int(significant)
    if value > 1000:
        return None

    return -value if negative else value


def parse_price(field):
    if not field or not field.isdigit():
        return None

    significant = field.lstrip(b'0')
    if not significant:
        return 0

    if len(significant) > 8:
        return None

    value = int(significant)
    if value > 10000000:
        return None

    return value


def main():
    data = sys.stdin.buffer.read()

    if data == b"":
        sys.stdout.write("rows 0 bad 0 groups 0\ntotal 0\n")
        return

    lines = data.split(b'\n')
    if lines[-1] == b'':
        lines.pop()

    groups = {}
    good = 0
    bad = 0

    for line in lines[1:]:
        fields = line.split(b',')

        if len(fields) != 4:
            bad += 1
            continue

        region, product, qty_field, price_field = fields

        if not NAME_RE.fullmatch(region) or not NAME_RE.fullmatch(product):
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

        key = (region, product)
        entry = groups.get(key)

        if entry is None:
            groups[key] = [qty, qty * price]
        else:
            entry[0] += qty
            entry[1] += qty * price

        good += 1

    region_totals = {}
    for (region, _product), (_qty, revenue) in groups.items():
        region_totals[region] = region_totals.get(region, 0) + revenue

    output = [f"rows {good} bad {bad} groups {len(groups)}"]

    top = sorted(
        groups.items(),
        key=lambda item: (-item[1][1], item[0][0], item[0][1])
    )[:10]

    for (region, product), (qty_sum, revenue) in top:
        output.append(
            f"{region.decode('ascii')} {product.decode('ascii')} "
            f"{qty_sum} {revenue}"
        )

    for region in sorted(region_totals):
        output.append(
            f"region {region.decode('ascii')} revenue {region_totals[region]}"
        )

    output.append(f"total {sum(region_totals.values())}")

    sys.stdout.write("\n".join(output) + "\n")


if __name__ == "__main__":
    main()
