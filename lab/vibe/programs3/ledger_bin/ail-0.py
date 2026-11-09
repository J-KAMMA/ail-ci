import sys


def fail(offset, kind):
    sys.stdout.write("error at offset " + str(offset) + ": " + kind + "\n")
    sys.exit(2)


def read_var(data, pos, size):
    value = 0
    shift = 0
    count = 0
    while True:
        if pos >= size:
            return 0, pos, "truncated"
        b = data[pos]
        pos = pos + 1
        count = count + 1
        if count == 5 and (b & 0x80) != 0:
            return 0, pos, "varint"
        value = value | ((b & 0x7F) << shift)
        if (b & 0x80) == 0:
            if count >= 2 and b == 0:
                return 0, pos, "varint"
            if value > 4294967295:
                return 0, pos, "varint"
            return value, pos, None
        shift = shift + 7


def parse(data):
    size = len(data)

    if size < 6:
        fail(0, "header")

    if (data[0] != 0xC7 or data[1] != 0x4C or data[2] != 0x58 or
            data[3] != 0x46 or data[4] != 0x02 or (data[5] & 0xFE) != 0):
        fail(0, "header")

    strict = (data[5] & 1) != 0
    pos = 6
    records = []

    while pos < size:
        start = pos
        op = data[pos]
        pos = pos + 1

        if op < 1 or op > 5:
            fail(start, "opcode")

        if op == 1:
            aid, pos, e = read_var(data, pos, size)
            if e is not None:
                fail(start, e)

            if pos >= size:
                fail(start, "truncated")
            name_len = data[pos]
            pos = pos + 1

            if name_len < 1 or name_len > 32:
                fail(start, "name")

            name_start = pos
            i = 0
            while i < name_len:
                if pos >= size:
                    fail(start, "truncated")
                nb = data[pos]
                pos = pos + 1
                if nb < 0x21 or nb > 0x7E:
                    fail(start, "name")
                i = i + 1

            name = data[name_start:pos].decode("ascii")

            initial, pos, e = read_var(data, pos, size)
            if e is not None:
                fail(start, e)

            records.append((start, op, aid, name, initial))

        elif op == 2:
            frm, pos, e = read_var(data, pos, size)
            if e is not None:
                fail(start, e)

            to, pos, e = read_var(data, pos, size)
            if e is not None:
                fail(start, e)

            amount, pos, e = read_var(data, pos, size)
            if e is not None:
                fail(start, e)

            records.append((start, op, frm, to, amount))

        elif op == 3:
            aid, pos, e = read_var(data, pos, size)
            if e is not None:
                fail(start, e)

            records.append((start, op, aid))

        elif op == 4:
            aid, pos, e = read_var(data, pos, size)
            if e is not None:
                fail(start, e)

            amount, pos, e = read_var(data, pos, size)
            if e is not None:
                fail(start, e)

            records.append((start, op, aid, amount))

        else:
            length, pos, e = read_var(data, pos, size)
            if e is not None:
                fail(start, e)

            if pos + length > size:
                fail(start, "truncated")
            pos = pos + length

            records.append((start, op, length))

        if pos >= size:
            fail(start, "truncated")

        check_byte = data[pos]
        pos = pos + 1

        c = 0
        i = start
        while i < pos - 1:
            c = (c * 31 + data[i]) % 251
            i = i + 1

        if c != check_byte:
            fail(start, "check")

    return strict, records


def replay(records, strict):
    accounts = {}
    open_count = 0
    shut_count = 0
    dup = 0
    unknown = 0
    shut_rej = 0
    self_rej = 0
    funds = 0
    total = 0

    for rec in records:
        start = rec[0]
        op = rec[1]
        reason = None

        if op == 1:
            aid = rec[2]
            name = rec[3]
            initial = rec[4]

            if aid in accounts:
                reason = "dup"
            else:
                accounts[aid] = [1, name, initial]
                open_count = open_count + 1
                total = total + initial

        elif op == 2:
            frm = rec[2]
            to = rec[3]
            amount = rec[4]

            if frm not in accounts:
                reason = "unknown"
            elif to not in accounts:
                reason = "unknown"
            elif accounts[frm][0] == 0:
                reason = "shut"
            elif accounts[to][0] == 0:
                reason = "shut"
            elif frm == to:
                reason = "self"
            elif amount > accounts[frm][2]:
                reason = "funds"
            else:
                accounts[frm][2] = accounts[frm][2] - amount
                accounts[to][2] = accounts[to][2] + amount

        elif op == 3:
            aid = rec[2]

            if aid not in accounts:
                reason = "unknown"
            elif accounts[aid][0] == 0:
                reason = "shut"
            else:
                accounts[aid][0] = 0
                open_count = open_count - 1
                shut_count = shut_count + 1

        elif op == 4:
            aid = rec[2]
            amount = rec[3]

            if aid not in accounts:
                reason = "unknown"
            elif accounts[aid][0] == 0:
                reason = "shut"
            else:
                accounts[aid][2] = accounts[aid][2] + amount
                total = total + amount

        if reason is not None:
            if strict:
                sys.stdout.write("rejected at offset " + str(start) + ": " + reason + "\n")
                sys.exit(3)

            if reason == "dup":
                dup = dup + 1
            elif reason == "unknown":
                unknown = unknown + 1
            elif reason == "shut":
                shut_rej = shut_rej + 1
            elif reason == "self":
                self_rej = self_rej + 1
            else:
                funds = funds + 1

    return (accounts, open_count, shut_count, dup, unknown,
            shut_rej, self_rej, funds, total)


def print_summary(record_count, accounts, open_count, shut_count,
                  dup, unknown, shut_rej, self_rej, funds, total):
    lines = []

    lines.append("records: " + str(record_count))
    lines.append("accounts: " + str(open_count) + " open, " + str(shut_count) + " shut")
    lines.append("rejected: dup=" + str(dup) +
                 " unknown=" + str(unknown) +
                 " shut=" + str(shut_rej) +
                 " self=" + str(self_rej) +
                 " funds=" + str(funds))
    lines.append("total: " + str(total))

    top = []
    for aid in accounts:
        acct = accounts[aid]
        if acct[0] == 1:
            top.append((-acct[2], aid, acct[1]))
    top.sort()

    i = 0
    while i < len(top) and i < 5:
        negbal, aid, name = top[i]
        lines.append("top: " + str(aid) + " " + name + " " + str(-negbal))
        i = i + 1

    digest = 0
    ids = sorted(accounts.keys())
    for aid in ids:
        acct = accounts[aid]
        digest = (digest * 1000003 + aid * 7 + acct[2]) % 1000000007

    lines.append("digest: " + str(digest))

    sys.stdout.write("\n".join(lines) + "\n")


def main():
    if len(sys.argv) != 2:
        sys.exit(1)

    try:
        with open(sys.argv[1], "rb") as f:
            data = f.read()
    except OSError:
        sys.exit(1)

    strict, records = parse(data)
    accounts, open_count, shut_count, dup, unknown, shut_rej, self_rej, funds, total = replay(records, strict)

    print_summary(len(records), accounts, open_count, shut_count,
                  dup, unknown, shut_rej, self_rej, funds, total)
    sys.exit(0)


main()
