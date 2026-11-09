import sys

MASK32 = 4294967295
MAGIC = b'\xc7LXF'


class StructErr(Exception):
    def __init__(self, offset, kind):
        self.offset = offset
        self.kind = kind


def parse_var(data, pos, rec):
    n = len(data)
    value = 0
    shift = 0
    count = 0
    last = 0
    while True:
        if pos >= n:
            raise StructErr(rec, 'truncated')
        b = data[pos]
        pos += 1
        count += 1
        last = b
        value |= (b & 0x7F) << shift
        shift += 7
        if b & 0x80:
            if count == 5:
                raise StructErr(rec, 'varint')
        else:
            break
    if count >= 2 and last == 0:
        raise StructErr(rec, 'varint')
    if value > MASK32:
        raise StructErr(rec, 'varint')
    return value, pos


def parse(data):
    n = len(data)
    if (n < 6 or data[0] != 0xC7 or data[1:4] != b'LXF'
            or data[4] != 0x02 or data[5] not in (0, 1)):
        raise StructErr(0, 'header')
    strict = (data[5] & 1) == 1
    pos = 6
    records = []
    while pos < n:
        start = pos
        op = data[pos]
        pos += 1
        if op < 1 or op > 5:
            raise StructErr(start, 'opcode')

        if op == 1:
            aid, pos = parse_var(data, pos, start)
            if pos >= n:
                raise StructErr(start, 'truncated')
            nl = data[pos]
            pos += 1
            if nl < 1 or nl > 32:
                raise StructErr(start, 'name')
            nb = bytearray()
            for _ in range(nl):
                if pos >= n:
                    raise StructErr(start, 'truncated')
                c = data[pos]
                pos += 1
                if c < 0x21 or c > 0x7E:
                    raise StructErr(start, 'name')
                nb.append(c)
            initial, pos = parse_var(data, pos, start)
            records.append((start, op, (aid, nb.decode('ascii'), initial)))

        elif op == 2:
            frm, pos = parse_var(data, pos, start)
            to, pos = parse_var(data, pos, start)
            amt, pos = parse_var(data, pos, start)
            records.append((start, op, (frm, to, amt)))

        elif op == 3:
            aid, pos = parse_var(data, pos, start)
            records.append((start, op, (aid,)))

        elif op == 4:
            aid, pos = parse_var(data, pos, start)
            amt, pos = parse_var(data, pos, start)
            records.append((start, op, (aid, amt)))

        else:
            ln, pos = parse_var(data, pos, start)
            if pos + ln > n:
                raise StructErr(start, 'truncated')
            pos += ln
            records.append((start, op, ()))

        if pos >= n:
            raise StructErr(start, 'truncated')
        c = 0
        for i in range(start, pos):
            c = (c * 31 + data[i]) % 251
        if data[pos] != c:
            raise StructErr(start, 'check')
        pos += 1

    return strict, records


def replay(strict, records):
    accounts = {}
    counts = {'dup': 0, 'unknown': 0, 'shut': 0, 'self': 0, 'funds': 0}

    for start, op, fields in records:
        reason = None

        if op == 1:
            aid, name, initial = fields
            if aid in accounts:
                reason = 'dup'
            else:
                accounts[aid] = [name, initial, True]

        elif op == 2:
            frm, to, amt = fields
            if frm not in accounts:
                reason = 'unknown'
            elif to not in accounts:
                reason = 'unknown'
            elif not accounts[frm][2]:
                reason = 'shut'
            elif not accounts[to][2]:
                reason = 'shut'
            elif frm == to:
                reason = 'self'
            elif amt > accounts[frm][1]:
                reason = 'funds'
            else:
                accounts[frm][1] -= amt
                accounts[to][1] += amt

        elif op == 3:
            (aid,) = fields
            if aid not in accounts:
                reason = 'unknown'
            elif not accounts[aid][2]:
                reason = 'shut'
            else:
                accounts[aid][2] = False

        elif op == 4:
            aid, amt = fields
            if aid not in accounts:
                reason = 'unknown'
            elif not accounts[aid][2]:
                reason = 'shut'
            else:
                accounts[aid][1] += amt

        if reason is not None:
            counts[reason] += 1
            if strict:
                sys.stdout.write(f"rejected at offset {start}: {reason}\n")
                return None

    return accounts, counts


def emit(records, accounts, counts):
    a_open = 0
    for v in accounts.values():
        if v[2]:
            a_open += 1
    a_shut = len(accounts) - a_open
    total = 0
    for v in accounts.values():
        total += v[1]

    out = []
    out.append(f"records: {len(records)}")
    out.append(f"accounts: {a_open} open, {a_shut} shut")
    out.append(
        "rejected: dup={} unknown={} shut={} self={} funds={}".format(
            counts['dup'], counts['unknown'], counts['shut'],
            counts['self'], counts['funds']
        )
    )
    out.append(f"total: {total}")

    opens = [(aid, v[0], v[1]) for aid, v in accounts.items() if v[2]]
    opens.sort(key=lambda t: (-t[2], t[0]))
    for aid, name, bal in opens[:5]:
        out.append(f"top: {aid} {name} {bal}")

    g = 0
    for aid in sorted(accounts):
        g = (g * 1000003 + aid * 7 + accounts[aid][1]) % 1000000007
    out.append(f"digest: {g}")

    sys.stdout.write("\n".join(out) + "\n")


def main():
    if len(sys.argv) != 2:
        sys.exit(1)
    try:
        with open(sys.argv[1], 'rb') as f:
            data = f.read()
    except Exception:
        sys.exit(1)

    try:
        strict, records = parse(data)
    except StructErr as e:
        sys.stdout.write(f"error at offset {e.offset}: {e.kind}\n")
        sys.exit(2)

    result = replay(strict, records)
    if result is None:
        sys.exit(3)

    accounts, counts = result
    emit(records, accounts, counts)
    sys.exit(0)


if __name__ == '__main__':
    main()
