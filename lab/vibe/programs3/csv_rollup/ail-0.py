import sys


DIGIT_VALUE = {
    '0': 0, '1': 1, '2': 2, '3': 3, '4': 4,
    '5': 5, '6': 6, '7': 7, '8': 8, '9': 9,
}


def valid_name(s):
    n = len(s)
    if n < 1 or n > 16:
        return False
    i = 0
    while i < n:
        c = s[i]
        if c >= 'a' and c <= 'z':
            i += 1
            continue
        if c >= '0' and c <= '9':
            i += 1
            continue
        if c == '_':
            i += 1
            continue
        return False
    return True


def parse_qty(s):
    n = len(s)
    if n == 0:
        return None
    i = 0
    neg = False
    if s[0] == '-':
        neg = True
        i = 1
    if i >= n:
        return None
    val = 0
    while i < n:
        c = s[i]
        if c < '0' or c > '9':
            return None
        val = val * 10 + DIGIT_VALUE[c]
        if val > 1000:
            return None
        i += 1
    if neg:
        return -val
    return val


def parse_price(s):
    n = len(s)
    if n == 0:
        return None
    val = 0
    i = 0
    while i < n:
        c = s[i]
        if c < '0' or c > '9':
            return None
        val = val * 10 + DIGIT_VALUE[c]
        if val > 10000000:
            return None
        i += 1
    return val


def main():
    data = sys.stdin.buffer.read()
    if len(data) == 0:
        sys.stdout.write("rows 0 bad 0 groups 0\ntotal 0\n")
        return

    text = data.decode('latin-1')
    lines = text.split('\n')
    if len(lines) > 0 and lines[len(lines) - 1] == '':
        lines.pop()

    good = 0
    bad = 0
    qty_sums = {}
    revenues = {}
    order = []

    nlines = len(lines)
    i = 1
    while i < nlines:
        line = lines[i]
        i += 1
        fields = line.split(',')
        if len(fields) != 4:
            bad += 1
            continue
        region = fields[0]
        product = fields[1]
        if not valid_name(region) or not valid_name(product):
            bad += 1
            continue
        qty = parse_qty(fields[2])
        if qty is None:
            bad += 1
            continue
        price = parse_price(fields[3])
        if price is None:
            bad += 1
            continue

        key = (region, product)
        if key in qty_sums:
            qty_sums[key] = qty_sums[key] + qty
            revenues[key] = revenues[key] + qty * price
        else:
            qty_sums[key] = qty
            revenues[key] = qty * price
            order.append(key)
        good += 1

    entries = []
    for key in order:
        entries.append((-revenues[key], key[0], key[1], key))
    entries.sort()

    keys = []
    for e in entries:
        keys.append(e[3])

    region_sums = {}
    for key in keys:
        r = key[0]
        if r in region_sums:
            region_sums[r] = region_sums[r] + revenues[key]
        else:
            region_sums[r] = revenues[key]

    out = []
    out.append("rows %d bad %d groups %d\n" % (good, bad, len(keys)))

    limit = 10
    if len(keys) < limit:
        limit = len(keys)
    j = 0
    while j < limit:
        k = keys[j]
        out.append("%s %s %d %d\n" % (k[0], k[1], qty_sums[k], revenues[k]))
        j += 1

    region_names = list(region_sums.keys())
    region_names.sort()

    total = 0
    for r in region_names:
        out.append("region %s revenue %d\n" % (r, region_sums[r]))
        total = total + region_sums[r]

    out.append("total %d\n" % total)
    sys.stdout.write("".join(out))


main()
