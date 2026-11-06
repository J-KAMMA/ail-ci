import sys


class ParseError(Exception):
    __slots__ = ("offset", "kind")

    def __init__(self, offset, kind):
        self.offset = offset
        self.kind = kind


def read_var(data, pos, n, start):
    value = 0
    shift = 0
    count = 0
    last = 0

    while True:
        if pos >= n:
            raise ParseError(start, "truncated")

        b = data[pos]
        pos += 1
        count += 1
        value |= (b & 0x7F) << shift

        if count == 5 and (b & 0x80):
            raise ParseError(start, "varint")

        if not (b & 0x80):
            last = b
            break

        shift += 7

    if count >= 2 and last == 0:
        raise ParseError(start, "varint")

    if value > 0xFFFFFFFF:
        raise ParseError(start, "varint")

    return value, pos


def parse_file(data):
    n = len(data)

    if n < 6:
        raise ParseError(0, "header")

    if data[:4] != b"\xC7LXF" or data[4] != 2 or data[5] not in (0, 1):
        raise ParseError(0, "header")

    strict = (data[5] & 1) != 0
    pos = 6
    records = []

    while pos < n:
        start = pos
        opcode = data[pos]
        pos += 1

        if opcode < 1 or opcode > 5:
            raise ParseError(start, "opcode")

        if opcode == 1:
            account_id, pos = read_var(data, pos, n, start)

            if pos >= n:
                raise ParseError(start, "truncated")

            name_len = data[pos]
            pos += 1

            if name_len < 1 or name_len > 32:
                raise ParseError(start, "name")

            name = bytearray()
            for _ in range(name_len):
                if pos >= n:
                    raise ParseError(start, "truncated")

                c = data[pos]
                pos += 1

                if c < 0x21 or c > 0x7E:
                    raise ParseError(start, "name")

                name.append(c)

            initial, pos = read_var(data, pos, n, start)
            fields = (account_id, bytes(name).decode("ascii"), initial)

        elif opcode == 2:
            from_id, pos = read_var(data, pos, n, start)
            to_id, pos = read_var(data, pos, n, start)
            amount, pos = read_var(data, pos, n, start)
            fields = (from_id, to_id, amount)

        elif opcode == 3:
            account_id, pos = read_var(data, pos, n, start)
            fields = (account_id,)

        elif opcode == 4:
            account_id, pos = read_var(data, pos, n, start)
            amount, pos = read_var(data, pos, n, start)
            fields = (account_id, amount)

        else:
            length, pos = read_var(data, pos, n, start)

            if pos + length > n:
                raise ParseError(start, "truncated")

            pos += length
            fields = ()

        if pos >= n:
            raise ParseError(start, "truncated")

        check_byte = data[pos]
        pos += 1

        c = 0
        for i in range(start, pos - 1):
            c = (c * 31 + data[i]) % 251

        if c != check_byte:
            raise ParseError(start, "check")

        records.append((start, opcode, fields))

    return records, strict


def main():
    if len(sys.argv) != 2:
        return 1

    try:
        with open(sys.argv[1], "rb") as f:
            data = f.read()
    except OSError:
        return 1

    try:
        records, strict = parse_file(data)
    except ParseError as e:
        sys.stdout.write(f"error at offset {e.offset}: {e.kind}\n")
        return 2

    accounts = {}
    counts = {
        "dup": 0,
        "unknown": 0,
        "shut": 0,
        "self": 0,
        "funds": 0,
    }

    for offset, opcode, fields in records:
        reason = None

        if opcode == 1:
            account_id, name, initial = fields

            if account_id in accounts:
                reason = "dup"
            else:
                accounts[account_id] = [name, initial, True]

        elif opcode == 2:
            from_id, to_id, amount = fields

            if from_id not in accounts or to_id not in accounts:
                reason = "unknown"
            elif not accounts[from_id][2] or not accounts[to_id][2]:
                reason = "shut"
            elif from_id == to_id:
                reason = "self"
            elif amount > accounts[from_id][1]:
                reason = "funds"
            else:
                accounts[from_id][1] -= amount
                accounts[to_id][1] += amount

        elif opcode == 3:
            account_id = fields[0]

            if account_id not in accounts:
                reason = "unknown"
            elif not accounts[account_id][2]:
                reason = "shut"
            else:
                accounts[account_id][2] = False

        elif opcode == 4:
            account_id, amount = fields

            if account_id not in accounts:
                reason = "unknown"
            elif not accounts[account_id][2]:
                reason = "shut"
            else:
                accounts[account_id][1] += amount

        if reason is not None:
            counts[reason] += 1

            if strict:
                sys.stdout.write(f"rejected at offset {offset}: {reason}\n")
                return 3

    open_count = 0
    shut_count = 0
    total = 0
    open_accounts = []

    for account_id, account in accounts.items():
        name, balance, is_open = account
        total += balance

        if is_open:
            open_count += 1
            open_accounts.append((balance, account_id, name))
        else:
            shut_count += 1

    open_accounts.sort(key=lambda item: (-item[0], item[1]))

    digest = 0
    for account_id in sorted(accounts):
        balance = accounts[account_id][1]
        digest = (digest * 1000003 + account_id * 7 + balance) % 1000000007

    output = []
    output.append(f"records: {len(records)}")
    output.append(f"accounts: {open_count} open, {shut_count} shut")
    output.append(
        f"rejected: dup={counts['dup']} unknown={counts['unknown']} "
        f"shut={counts['shut']} self={counts['self']} funds={counts['funds']}"
    )
    output.append(f"total: {total}")

    for balance, account_id, name in open_accounts[:5]:
        output.append(f"top: {account_id} {name} {balance}")

    output.append(f"digest: {digest}")

    sys.stdout.write("\n".join(output) + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
