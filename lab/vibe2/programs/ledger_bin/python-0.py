import sys


def main():
    if len(sys.argv) != 2:
        sys.exit(1)

    try:
        with open(sys.argv[1], "rb") as f:
            data = f.read()
    except OSError:
        sys.exit(1)

    n = len(data)

    if (
        n < 6
        or data[:4] != b"\xc7LXF"
        or data[4] != 2
        or (data[5] & 0xFE) != 0
    ):
        sys.stdout.write("error at offset 0: header\n")
        sys.exit(2)

    strict = (data[5] & 1) != 0
    view = memoryview(data)

    def fail(offset, kind):
        sys.stdout.write(f"error at offset {offset}: {kind}\n")
        sys.exit(2)

    def read_var(pos, record_start):
        value = 0
        shift = 0

        for i in range(5):
            if pos >= n:
                fail(record_start, "truncated")

            b = data[pos]
            pos += 1
            value |= (b & 0x7F) << shift

            if b & 0x80:
                if i == 4:
                    fail(record_start, "varint")
                shift += 7
            else:
                if i >= 1 and b == 0:
                    fail(record_start, "varint")
                if value > 0xFFFFFFFF:
                    fail(record_start, "varint")
                return value, pos

        fail(record_start, "varint")

    def checksum(start, end):
        c = 0
        for b in view[start:end]:
            c = (c * 31 + b) % 251
        return c

    records = []
    pos = 6

    while pos < n:
        record_start = pos
        opcode = data[pos]
        pos += 1

        if opcode < 1 or opcode > 5:
            fail(record_start, "opcode")

        if opcode == 1:
            account_id, pos = read_var(pos, record_start)

            if pos >= n:
                fail(record_start, "truncated")
            name_len = data[pos]
            pos += 1

            if name_len < 1 or name_len > 32:
                fail(record_start, "name")

            name = bytearray()
            for _ in range(name_len):
                if pos >= n:
                    fail(record_start, "truncated")
                ch = data[pos]
                pos += 1
                if ch < 0x21 or ch > 0x7E:
                    fail(record_start, "name")
                name.append(ch)

            initial, pos = read_var(pos, record_start)
            fields = (account_id, bytes(name), initial)

        elif opcode == 2:
            source, pos = read_var(pos, record_start)
            target, pos = read_var(pos, record_start)
            amount, pos = read_var(pos, record_start)
            fields = (source, target, amount)

        elif opcode == 3:
            account_id, pos = read_var(pos, record_start)
            fields = (account_id,)

        elif opcode == 4:
            account_id, pos = read_var(pos, record_start)
            amount, pos = read_var(pos, record_start)
            fields = (account_id, amount)

        else:
            note_len, pos = read_var(pos, record_start)
            if n - pos < note_len:
                fail(record_start, "truncated")
            pos += note_len
            fields = (note_len,)

        if pos >= n:
            fail(record_start, "truncated")

        check_byte = data[pos]
        pos += 1

        if check_byte != checksum(record_start, pos - 1):
            fail(record_start, "check")

        records.append((opcode, record_start, fields))

    accounts = {}
    dup = unknown = shut = self_count = funds = 0

    for opcode, offset, fields in records:
        reason = None

        if opcode == 1:
            account_id, name, initial = fields
            if account_id in accounts:
                reason = "dup"
            else:
                accounts[account_id] = [name, initial, True]

        elif opcode == 2:
            source, target, amount = fields

            if source not in accounts:
                reason = "unknown"
            elif target not in accounts:
                reason = "unknown"
            elif not accounts[source][2]:
                reason = "shut"
            elif not accounts[target][2]:
                reason = "shut"
            elif source == target:
                reason = "self"
            elif amount > accounts[source][1]:
                reason = "funds"
            else:
                accounts[source][1] -= amount
                accounts[target][1] += amount

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
            if strict:
                sys.stdout.write(f"rejected at offset {offset}: {reason}\n")
                sys.exit(3)

            if reason == "dup":
                dup += 1
            elif reason == "unknown":
                unknown += 1
            elif reason == "shut":
                shut += 1
            elif reason == "self":
                self_count += 1
            else:
                funds += 1

    open_ids = [account_id for account_id, account in accounts.items() if account[2]]
    open_count = len(open_ids)
    shut_count = len(accounts) - open_count

    total = sum(account[1] for account in accounts.values())

    lines = [
        f"records: {len(records)}",
        f"accounts: {open_count} open, {shut_count} shut",
        f"rejected: dup={dup} unknown={unknown} shut={shut} self={self_count} funds={funds}",
        f"total: {total}",
    ]

    top_ids = sorted(open_ids, key=lambda account_id: (-accounts[account_id][1], account_id))[:5]

    for account_id in top_ids:
        name = accounts[account_id][0].decode("ascii")
        balance = accounts[account_id][1]
        lines.append(f"top: {account_id} {name} {balance}")

    digest = 0
    for account_id in sorted(accounts):
        digest = (
            digest * 1000003 + account_id * 7 + accounts[account_id][1]
        ) % 1000000007

    lines.append(f"digest: {digest}")

    sys.stdout.write("\n".join(lines) + "\n")


if __name__ == "__main__":
    main()
