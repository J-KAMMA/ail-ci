import sys


def valid_name(s):
    if len(s) < 1 or len(s) > 16:
        return False
    for c in s:
        if not (('a' <= c <= 'z') or ('0' <= c <= '9') or c == '_'):
            return False
    return True


def parse_int(s, allow_neg, lo, hi):
    n = len(s)
    i = 0
    neg = False
    if allow_neg and n > 0 and s[0] == '-':
        neg = True
        i = 1
    if i >= n:
        return None
    start = i
    while i < n:
        c = s[i]
        if c < '0' or c > '9':
            return None
        i += 1
    digits = s[start:].lstrip('0')
    if len(digits) > len(str(hi)):
        return None
    v = int(digits) if digits else 0
    if neg:
        v = -v
    if v < lo or v > hi:
        return None
    return v


def main():
    data = sys.stdin.buffer.read().decode('latin-1')

    lines = data.split('\n')
    if len(lines) > 0 and lines[-1] == '':
        lines.pop()

    groups = {}
    bad = 0
    good = 0
    nlines = len(lines)

    for idx in range(1, nlines):
        parts = lines[idx].split(',')
        if len(parts) != 4:
            bad += 1
            continue
        r = parts[0]
        p = parts[1]
        qs = parts[2]
        ps = parts[3]
        if not valid_name(r) or not valid_name(p):
            bad += 1
            continue
        q = parse_int(qs, True, -1000, 1000)
        if q is None:
            bad += 1
            continue
        pr = parse_int(ps, False, 0, 10000000)
        if pr is None:
            bad += 1
            continue

        good += 1
        key = (r, p)
        cur = groups.get(key)
        if cur is None:
            groups[key] = [q, q * pr]
        else:
            cur[0] += q
            cur[1] += q * pr

    out = []
    out.append("rows " + str(good) + " bad " + str(bad) + " groups " + str(len(groups)))

    items = sorted(groups.items(), key=lambda kv: (-kv[1][1], kv[0][0], kv[0][1]))
    limit = 10 if len(items) > 10 else len(items)
    for i in range(limit):
        (r, p), vals = items[i]
        out.append(r + " " + p + " " + str(vals[0]) + " " + str(vals[1]))

    region_sum = {}
    total = 0
    for (r, p), vals in groups.items():
        rev = vals[1]
        total += rev
        region_sum[r] = region_sum.get(r, 0) + rev

    for r in sorted(region_sum.keys()):
        out.append("region " + r + " revenue " + str(region_sum[r]))

    out.append("total " + str(total))

    sys.stdout.write('\n'.join(out) + '\n')


main()
