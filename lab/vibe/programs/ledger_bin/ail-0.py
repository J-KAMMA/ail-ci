import sys


def read_var(data, pos, n):
    value = 0
    shift = 0
    count = 0
    while True:
        if pos >= n:
            return ('truncated', 0, pos)
        b = data[pos]
        pos += 1
        count += 1
        value |= (b & 0x7f) << shift
        if count == 5 and (b & 0x80):
            return ('varint', 0, pos)
        if b & 0x80:
            shift += 7
        else:
            break
    if count >= 2 and b == 0:
        return ('varint', 0, pos)
    if value > 4294967295:
        return ('varint', 0, pos)
    return ('ok', value, pos)


def structural_error(offset, kind):
    sys.stdout.write("error at offset %d: %s\n" % (offset, kind))
    sys.exit(2)


def main():
    if len(sys.argv) != 2:
        sys.exit(1)
    try:
        with open(sys.argv[1], 'rb') as f:
            data = f.read()
    except OSError:
        sys.exit(1)

    n = len(data)
    if (n < 6 or data[0] != 0xC7 or data[1] != 0x4C or data[2] != 0x58 or
            data[3] != 0x46 or data[4] != 2 or (data[5] & 0xFE) != 0):
        structural_error(0, 'header')

    strict = (data[5] & 1) != 0

    records = []
    pos = 6
    while pos < n:
        start = pos
        op = data[pos]
        pos += 1
        if op < 1 or op > 5:
            structural_error(start, 'opcode')

        if op == 1:
            st, v, pos = read_var(data, pos, n)
            if st != 'ok':
                structural_error(start, st)
            rid = v
            if pos >= n:
                structural_error(start, 'truncated')
            name_len = data[pos]
            pos += 1
            if name_len < 1 or name_len > 32:
                structural_error(start, 'name')
            name_bytes = []
            for _ in range(name_len):
                if pos >= n:
                    structural_error(start, 'truncated')
                b = data[pos]
                pos += 1
                if b < 0x21 or b > 0x7E:
                    structural_error(start, 'name')
                name_bytes.append(b)
            st, v, pos = read_var(data, pos, n)
            if st != 'ok':
                structural_error(start, st)
            initial = v
            fields = (rid, bytes(name_bytes), initial)
            records.append((start, op, fields))
        elif op == 2:
            st, frm, pos = read_var(data, pos, n)
            if st != 'ok':
                structural_error(start, st)
            st, to, pos = read_var(data, pos, n)
            if st != 'ok':
                structural_error(start, st)
            st, amount, pos = read_var(data, pos, n)
            if st != 'ok':
                structural_error(start, st)
            records.append((start, op, (frm, to, amount)))
        elif op == 3:
            st, rid, pos = read_var(data, pos, n)
            if st != 'ok':
                structural_error(start, st)
            records.append((start, op, (rid,)))
        elif op == 4:
            st, rid, pos = read_var(data, pos, n)
            if st != 'ok':
                structural_error(start, st)
            st, amount, pos = read_var(data, pos, n)
            if st != 'ok':
                structural_error(start, st)
            records.append((start, op, (rid, amount)))
        else:
            st, ln, pos = read_var(data, pos, n)
            if st != 'ok':
                structural_error(start, st)
            if ln > n - pos:
                structural_error(start, 'truncated')
            pos += ln
            records.append((start, op, (ln,)))

        if pos >= n:
            structural_error(start, 'truncated')
        cb = data[pos]
        pos += 1
        c = 0
        for i in range(start, pos - 1):
            c = (c * 31 + data[i]) % 251
        if c != cb:
            structural_error(start, 'check')

    accounts = {}
    dup = 0
    unknown = 0
    shuts = 0
    selfc = 0
    funds = 0

    for (start, op, f) in records:
        reason = None
        if op == 1:
            rid, name, initial = f
            if rid in accounts:
                reason = 'dup'
            else:
                accounts[rid] = [name, initial, True]
        elif op == 2:
            frm, to, amount = f
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
            elif amount > accounts[frm][1]:
                reason = 'funds'
            else:
                accounts[frm][1] -= amount
                accounts[to][1] += amount
        elif op == 3:
            rid = f[0]
            if rid not in accounts:
                reason = 'unknown'
            elif not accounts[rid][2]:
                reason = 'shut'
            else:
                accounts[rid][2] = False
        elif op == 4:
            rid, amount = f
            if rid not in accounts:
                reason = 'unknown'
            elif not accounts[rid][2]:
                reason = 'shut'
            else:
                accounts[rid][1] += amount
        else:
            pass

        if reason is not None:
            if strict:
                sys.stdout.write("rejected at offset %d: %s\n" % (start, reason))
                sys.exit(3)
            if reason == 'dup':
                dup += 1
            elif reason == 'unknown':
                unknown += 1
            elif reason == 'shut':
                shuts += 1
            elif reason == 'self':
                selfc += 1
            else:
                funds += 1

    open_count = 0
    shut_count = 0
    total = 0
    open_list = []
    ids = sorted(accounts.keys())
    g = 0
    for rid in ids:
        name, bal, is_open = accounts[rid]
        if is_open:
            open_count += 1
            open_list.append((rid, name, bal))
        else:
            shut_count += 1
        total += bal
        g = (g * 1000003 + rid * 7 + bal) % 1000000007

    open_list.sort(key=lambda x: (-x[2], x[0]))

    out = []
    out.append("records: %d" % len(records))
    out.append("accounts: %d open, %d shut" % (open_count, shut_count))
    out.append("rejected: dup=%d unknown=%d shut=%d self=%d funds=%d" %
               (dup, unknown, shuts, selfc, funds))
    out.append("total: %d" % total)
    for (rid, name, bal) in open_list[:5]:
        out.append("top: %d %s %d" % (rid, name.decode('ascii'), bal))
    out.append("digest: %d" % g)

    sys.stdout.write("\n".join(out) + "\n")
    sys.exit(0)


main()
