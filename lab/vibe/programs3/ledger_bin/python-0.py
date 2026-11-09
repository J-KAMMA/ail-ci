import sys


def parse_file(data):
    n = len(data)
    X = 0

    def error(kind):
        sys.stdout.write(f"error at offset {X}: {kind}\n")
        raise SystemExit(2)

    if n < 6:
        error('header')
    if data[0] != 0xC7 or data[1] != 0x4C or data[2] != 0x58 or data[3] != 0x46:
        error('header')
    if data[4] != 0x02:
        error('header')

    flags = data[5]
    if flags & 0xFE:
        error('header')
    strict = (flags & 0x01) != 0

    records = []
    pos = 6
    c = 0

    def read_var():
        nonlocal pos, c
        value = 0
        shift = 0

        for i in range(5):
            if pos >= n:
                error('truncated')

            b = data[pos]
            pos += 1
            c = (c * 31 + b) % 251

            value |= (b & 0x7F) << shift

            if b & 0x80:
                if i == 4:
                    error('varint')
                shift += 7
                continue

            if i > 0 and (b & 0x7F) == 0:
                error('varint')
            if value > 0xFFFFFFFF:
                error('varint')

            return value

        error('varint')

    while pos < n:
        X = pos
        op = data[pos]
        pos += 1

        if op < 1 or op > 5:
            error('opcode')

        c = op

        if op == 1:
            account_id = read_var()

            if pos >= n:
                error('truncated')
            name_len = data[pos]
            pos += 1
            c = (c * 31 + name_len) % 251

            if name_len < 1 or name_len > 32:
                error('name')

            name_bytes = bytearray()
            for _ in range(name_len):
                if pos >= n:
                    error('truncated')

                b = data[pos]
                pos += 1
                c = (c * 31 + b) % 251

                if b < 0x21 or b > 0x7E:
                    error('name')
                name_bytes.append(b)

            initial = read_var()
            rec = (1, X, account_id, name_bytes.decode('ascii'), initial)

        elif op == 2:
            src = read_var()
            dst = read_var()
            amount = read_var()
            rec = (2, X, src, dst, amount)

        elif op == 3:
            account_id = read_var()
            rec = (3, X, account_id)

        elif op == 4:
            account_id = read_var()
            amount = read_var()
            rec = (4, X, account_id, amount)

        else:
            length = read_var()

            if n - pos < length:
                error('truncated')

            end = pos + length
            for i in range(pos, end):
                c = (c * 31 + data[i]) % 251
            pos = end

            rec = (5, X)

        if pos >= n:
            error('truncated')

        check_byte = data[pos]
        pos += 1

        if check_byte != c:
            error('check')

        records.append(rec)

    return records, strict


def main():
    if len(sys.argv) != 2:
        return 1

    try:
        with open(sys.argv[1], 'rb') as f:
            data = f.read()
    except OSError:
        return 1

    records, strict = parse_file(data)

    accounts = {}
    open_count = 0
    shut_count = 0
    counts = {
        'dup': 0,
        'unknown': 0,
        'shut': 0,
        'self': 0,
        'funds': 0,
    }

    def reject(reason, offset):
        if strict:
            sys.stdout.write(f"rejected at offset {offset}: {reason}\n")
            raise SystemExit(3)
        counts[reason] += 1

    for rec in records:
        op = rec[0]

        if op == 1:
            _, offset, account_id, name, initial = rec

            if account_id in accounts:
                reject('dup', offset)
            else:
                accounts[account_id] = [True, name, initial]
                open_count += 1

        elif op == 2:
            _, offset, src, dst, amount = rec

            src_acc = accounts.get(src)
            if src_acc is None:
                reject('unknown', offset)
                continue

            dst_acc = accounts.get(dst)
            if dst_acc is None:
                reject('unknown', offset)
                continue

            if not src_acc[0]:
                reject('shut', offset)
                continue

            if not dst_acc[0]:
                reject('shut', offset)
                continue

            if src == dst:
                reject('self', offset)
                continue

            if amount > src_acc[2]:
                reject('funds', offset)
                continue

            src_acc[2] -= amount
            dst_acc[2] += amount

        elif op == 3:
            _, offset, account_id = rec
            acc = accounts.get(account_id)

            if acc is None:
                reject('unknown', offset)
            elif not acc[0]:
                reject('shut', offset)
            else:
                acc[0] = False
                open_count -= 1
                shut_count += 1

        elif op == 4:
            _, offset, account_id, amount = rec
            acc = accounts.get(account_id)

            if acc is None:
                reject('unknown', offset)
            elif not acc[0]:
                reject('shut', offset)
            else:
                acc[2] += amount

    total = sum(acc[2] for acc in accounts.values())

    open_accounts = [
        (account_id, acc[1], acc[2])
        for account_id, acc in accounts.items()
        if acc[0]
    ]
    open_accounts.sort(key=lambda item: (-item[2], item[0]))
    top = open_accounts[:5]

    digest = 0
    for account_id in sorted(accounts):
        digest = (
            digest * 1000003
            + account_id * 7
            + accounts[account_id][2]
        ) % 1000000007

    lines = []
    lines.append(f"records: {len(records)}")
    lines.append(f"accounts: {open_count} open, {shut_count} shut")
    lines.append(
        f"rejected: dup={counts['dup']} unknown={counts['unknown']} "
        f"shut={counts['shut']} self={counts['self']} funds={counts['funds']}"
    )
    lines.append(f"total: {total}")

    for account_id, name, balance in top:
        lines.append(f"top: {account_id} {name} {balance}")

    lines.append(f"digest: {digest}")

    sys.stdout.write("\n".join(lines) + "\n")
    return 0


if __name__ == '__main__':
    sys.exit(main())
