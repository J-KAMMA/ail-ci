import sys


def valid_ident(s: str) -> bool:
    n: int = len(s)
    if n < 1 or n > 16:
        return False
    i: int = 0
    while i < n:
        c: int = ord(s[i])
        if not ((c >= 97 and c <= 122) or (c >= 48 and c <= 57) or c == 95):
            return False
        i += 1
    return True


def parse_qty(s: str) -> int:
    n: int = len(s)
    if n == 0:
        return 1001
    start: int = 0
    neg: bool = False
    if s[0] == "-":
        neg = True
        start = 1
        if n == 1:
            return 1001
    value: int = 0
    i: int = start
    while i < n:
        c: int = ord(s[i])
        if c < 48 or c > 57:
            return 1001
        value = value * 10 + (c - 48)
        if value > 1000:
            return 1001
        i += 1
    if neg:
        return -value
    return value


def parse_price(s: str) -> int:
    n: int = len(s)
    if n == 0:
        return 10000001
    value: int = 0
    i: int = 0
    while i < n:
        c: int = ord(s[i])
        if c < 48 or c > 57:
            return 10000001
        value = value * 10 + (c - 48)
        if value > 10000000:
            return 10000001
        i += 1
    return value


def main() -> None:
    data: bytes = sys.stdin.buffer.read()
    text: str = data.decode("latin-1")

    good: int = 0
    bad: int = 0
    total_rev: int = 0
    qty_by: dict[tuple[str, str], int] = {}
    rev_by: dict[tuple[str, str], int] = {}

    if len(text) > 0:
        lines: list[str] = text.split("\n")
        if len(lines) > 0 and lines[len(lines) - 1] == "":
            lines.pop()

        i: int = 1
        while i < len(lines):
            line: str = lines[i]
            fields: list[str] = line.split(",")
            if len(fields) != 4:
                bad += 1
            else:
                region: str = fields[0]
                product: str = fields[1]
                qty_text: str = fields[2]
                price_text: str = fields[3]

                if not valid_ident(region):
                    bad += 1
                elif not valid_ident(product):
                    bad += 1
                elif qty_text == "" or price_text == "":
                    bad += 1
                else:
                    qty: int = parse_qty(qty_text)
                    price: int = parse_price(price_text)
                    if qty == 1001 or price == 10000001:
                        bad += 1
                    else:
                        good += 1
                        row_rev: int = qty * price
                        key: tuple[str, str] = (region, product)
                        if key in qty_by:
                            qty_by[key] = qty_by[key] + qty
                            rev_by[key] = rev_by[key] + row_rev
                        else:
                            qty_by[key] = qty
                            rev_by[key] = row_rev
                        total_rev = total_rev + row_rev
            i += 1

    groups: list[tuple[str, str]] = []
    for key in rev_by:
        groups.append(key)

    groups.sort()
    groups.sort(key=lambda k: rev_by[k], reverse=True)

    region_rev: dict[str, int] = {}
    for key in rev_by:
        region: str = key[0]
        if region in region_rev:
            region_rev[region] = region_rev[region] + rev_by[key]
        else:
            region_rev[region] = rev_by[key]

    regions: list[str] = []
    for region in region_rev:
        regions.append(region)
    regions.sort()

    print("rows", good, "bad", bad, "groups", len(groups))

    limit: int = len(groups)
    if limit > 10:
        limit = 10
    i = 0
    while i < limit:
        key = groups[i]
        print(key[0], key[1], qty_by[key], rev_by[key])
        i += 1

    for region in regions:
        print("region", region, "revenue", region_rev[region])

    print("total", total_rev)


if __name__ == "__main__":
    main()
