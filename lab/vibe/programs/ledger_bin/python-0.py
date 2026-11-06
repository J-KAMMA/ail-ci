import sys

MAGIC = b"\xc7LXF"
MAX_VAR = 4294967295


class StructError(Exception):
    def __init__(self, kind):
        self.kind = kind


def read_var(data, pos, n):
    value = 0
    shift = 0
    count = 0
    while True:
        if pos >= n:
            raise StructError("truncated")
        b = data[pos]
        pos += 1
        count += 1
        value |= (b & 0x7F) << shift
        if b & 0x80:
            if count == 5:
                raise StructError("varint")
            shift += 7
            continue
        break
    if count >= 2 and b == 0:
        raise StructError("varint")
    if value > MAX_VAR:
        raise StructError("varint")
    return value, pos


def parse_record(opcode, data, pos, n):
    if opcode == 1:  # OPEN
        aid, pos = read_var(data, pos, n)
        if pos >= n:
            raise StructError("truncated")
        name_len = data[pos]
        pos += 1
        if name_len < 1 or name_len > 32:
            raise StructError("name")
        buf = bytearray()
        for _ in range(name_len):
            if pos >= n:
                raise StructError("truncated")
            b = data[pos]
            pos += 1
            if b < 0x21 or b > 0x7E:
                raise StructError("name")
            buf.append(b)
        initial, pos = read_var(data, pos, n)
        return (aid, buf.decode("ascii"), initial), pos

    if opcode == 2:  # MOVE
        frm, pos = read_var(data, pos, n)
        to, pos = read_var(data, pos, n)
        amount, pos = read_var(data, pos, n)
        return (frm, to, amount), pos

    if opcode == 3:  # SHUT
        aid, pos = read_var(data, pos, n)
        return (aid,), pos

    if opcode == 4:  # MINT
        aid, pos = read_var(data, pos, n)
        amount, pos = read_var(data, pos, n)
        return (aid, amount), pos

    # opcode == 5, NOTE
    length, pos = read_var(data, pos, n)
    if n - pos < length:
        raise StructError("truncated")
    pos += length
    return (), pos


def main():
    argv = sys.argv[1:]
    if len(argv) != 1:
        sys.exit(1)

    try:
        with open(argv[0], "rb") as f:
            data = f.read()
    except OSError:
        sys.exit(1)

    n = len(data)

    if n < 6 or data[:4] != MAGIC or data[4] != 2 or (data[5] & 0xFE) != 0:
        sys.stdout.write("error at offset 0: header\n")
        sys.exit(2)

    strict = bool(data[5] & 1)

    pos = 6
    records = []

    while pos < n:
        start = pos
        try:
            opcode = data[pos]
            pos += 1
            if opcode < 1 or opcode > 5:
                raise StructError("opcode")
            fields, pos = parse_record(opcode, data, pos, n)
            cb = 0
            for b in data[start:pos]:
                cb = (cb * 31 + b) % 251
            if pos >= n:
                raise StructError("truncated")
            if data[pos] != cb:
                raise StructError("check")
            pos += 1
        except StructError as e:
            sys.stdout.write("error at offset %d: %s\n" % (start, e.kind))
            sys.exit(2)
        records.append((start, opcode, fields))

    accounts = {}
    rej = {"dup": 0, "unknown": 0, "shut": 0, "self": 0, "funds": 0}

    def reject(reason, off):
        rej[reason] += 1
        if strict:
            sys.stdout.write("rejected at offset %d: %s\n" % (off, reason))
            sys.exit(3)

    for start, opcode, fields in records:
        if opcode == 1:  # OPEN
            aid, name, initial = fields
            if aid in accounts:
                reject("dup", start)
            else:
                accounts[aid] = [name, initial, True]

        elif opcode == 2:  # MOVE
            frm, to, amount = fields
            if frm not in accounts:
                reject("unknown", start)
            elif to not in accounts:
                reject("unknown", start)
            elif not accounts[frm][2]:
                reject("shut", start)
            elif not accounts[to][2]:
                reject("shut", start)
            elif frm == to:
                reject("self", start)
            elif amount > accounts[frm][1]:
                reject("funds", start)
            else:
                accounts[frm][1] -= amount
                accounts[to][1] += amount

        elif opcode == 3:  # SHUT
            aid = fields[0]
            if aid not in accounts:
                reject("unknown", start)
            elif not accounts[aid][2]:
                reject("shut", start)
            else:
                accounts[aid][2] = False

        elif opcode == 4:  # MINT
            aid, amount = fields
            if aid not in accounts:
                reject("unknown", start)
            elif not accounts[aid][2]:
                reject("shut", start)
            else:
                accounts[aid][1] += amount

        # opcode 5, NOTE: nothing

    total_records = len(records)
    open_list = [(aid, v[0], v[1]) for aid, v in accounts.items() if v[2]]
    a_open = len(open_list)
    a_shut = len(accounts) - a_open
    total = sum(v[1] for v in accounts.values())

    top = sorted(open_list, key=lambda x: (-x[2], x[0]))[:5]

    g = 0
    for aid in sorted(accounts):
        g = (g * 1000003 + aid * 7 + accounts[aid][1]) % 1000000007

    lines = [
        "records: %d" % total_records,
        "accounts: %d open, %d shut" % (a_open, a_shut),
        "rejected: dup=%d unknown=%d shut=%d self=%d funds=%d"
        % (rej["dup"], rej["unknown"], rej["shut"], rej["self"], rej["funds"]),
        "total: %d" % total,
    ]
    for aid, name, bal in top:
        lines.append("top: %d %s %d" % (aid, name, bal))
    lines.append("digest: %d" % g)

    sys.stdout.write("\n".join(lines) + "\n")


if __name__ == "__main__":
    main()
