import sys


class StructuralError(Exception):
    def __init__(self, kind):
        self.kind = kind


def read_var(data, pos, n):
    val = 0
    shift = 0
    cnt = 0
    last = 0
    while True:
        if pos >= n:
            raise StructuralError('truncated')
        b = data[pos]
        pos += 1
        cnt += 1
        last = b
        val = val | ((b & 0x7F) << shift)
        if cnt == 5 and (b & 0x80) != 0:
            raise StructuralError('varint')
        if (b & 0x80) == 0:
            break
        shift += 7
    if cnt >= 2 and last == 0:
        raise StructuralError('varint')
    if val > 4294967295:
        raise StructuralError('varint')
    return val, pos


def main():
    if len(sys.argv) != 2:
        sys.exit(1)

    try:
        f = open(sys.argv[1], 'rb')
        data = f.read()
        f.close()
    except OSError:
        sys.exit(1)

    n = len(data)

    if n < 6:
        sys.stdout.write("error at offset 0: header\n")
        sys.exit(2)
    if data[0] != 0xC7 or data[1] != 0x4C or data[2] != 0x58 or data[3] != 0x46:
        sys.stdout.write("error at offset 0: header\n")
        sys.exit(2)
    if data[4] != 2:
        sys.stdout.write("error at offset 0: header\n")
        sys.exit(2)

    flags = data[5]
    if flags != 0 and flags != 1:
        sys.stdout.write("error at offset 0: header\n")
        sys.exit(2)

    records = []
    pos = 6
    err = None

    while pos < n:
        start = pos
        op = data[pos]
        pos += 1
        if op < 1 or op > 5:
            err = (start, 'opcode')
            break

        try:
            if op == 1:
                idv, pos = read_var(data, pos, n)
                if pos >= n:
                    raise StructuralError('truncated')
                nl = data[pos]
                pos += 1
                if nl < 1 or nl > 32:
                    raise StructuralError('name')
                chars = []
                for _ in range(nl):
                    if pos >= n:
                        raise StructuralError('truncated')
                    cb = data[pos]
                    pos += 1
                    if cb < 0x21 or cb > 0x7E:
                        raise StructuralError('name')
                    chars.append(chr(cb))
                name = ''.join(chars)
                initial, pos = read_var(data, pos, n)
                body = (idv, name, initial)

            elif op == 2:
                frm, pos = read_var(data, pos, n)
                to, pos = read_var(data, pos, n)
                amt, pos = read_var(data, pos, n)
                body = (frm, to, amt)

            elif op == 3:
                idv, pos = read_var(data, pos, n)
                body = (idv,)

            elif op == 4:
                idv, pos = read_var(data, pos, n)
                amt, pos = read_var(data, pos, n)
                body = (idv, amt)

            else:
                ln, pos = read_var(data, pos, n)
                if n - pos < ln:
                    raise StructuralError('truncated')
                pos += ln
                body = ()

            if pos >= n:
                raise StructuralError('truncated')

            c = 0
            i = start
            while i < pos:
                c = (c * 31 + data[i]) % 251
                i += 1
            if data[pos] != c:
                raise StructuralError('check')
            pos += 1

        except StructuralError as e:
            err = (start, e.kind)
            break

        records.append((start, op, body))

    if err is not None:
        sys.stdout.write("error at offset %d: %s\n" % (err[0], err[1]))
        sys.exit(2)

    names = {}
    balances = {}
    isopen = {}

    dup = 0
    unk = 0
    shutc = 0
    selfc = 0
    fundsc = 0

    strict = (flags & 1) == 1

    for rec in records:
        start = rec[0]
        op = rec[1]
        body = rec[2]
        reason = None

        if op == 1:
            idv = body[0]
            if idv in names:
                reason = 'dup'
            else:
                names[idv] = body[1]
                balances[idv] = body[2]
                isopen[idv] = True

        elif op == 2:
            frm = body[0]
            to = body[1]
            amt = body[2]
            if frm not in names:
                reason = 'unknown'
            elif to not in names:
                reason = 'unknown'
            elif not isopen[frm]:
                reason = 'shut'
            elif not isopen[to]:
                reason = 'shut'
            elif frm == to:
                reason = 'self'
            elif amt > balances[frm]:
                reason = 'funds'
            else:
                balances[frm] = balances[frm] - amt
                balances[to] = balances[to] + amt

        elif op == 3:
            idv = body[0]
            if idv not in names:
                reason = 'unknown'
            elif not isopen[idv]:
                reason = 'shut'
            else:
                isopen[idv] = False

        elif op == 4:
            idv = body[0]
            amt = body[1]
            if idv not in names:
                reason = 'unknown'
            elif not isopen[idv]:
                reason = 'shut'
            else:
                balances[idv] = balances[idv] + amt

        if reason is not None:
            if strict:
                sys.stdout.write("rejected at offset %d: %s\n" % (start, reason))
                sys.exit(3)
            if reason == 'dup':
                dup += 1
            elif reason == 'unknown':
                unk += 1
            elif reason == 'shut':
                shutc += 1
            elif reason == 'self':
                selfc += 1
            else:
                fundsc += 1

    total = 0
    open_count = 0
    shut_count = 0
    for idv in names:
        total += balances[idv]
        if isopen[idv]:
            open_count += 1
        else:
            shut_count += 1

    tops = []
    for idv in names:
        if isopen[idv]:
            tops.append((-balances[idv], idv, names[idv], balances[idv]))
    tops.sort()
    limit = 5
    if len(tops) < limit:
        limit = len(tops)

    g = 0
    ids = sorted(names.keys())
    for idv in ids:
        g = (g * 1000003 + idv * 7 + balances[idv]) % 1000000007

    lines = []
    lines.append("records: %d" % len(records))
    lines.append("accounts: %d open, %d shut" % (open_count, shut_count))
    lines.append("rejected: dup=%d unknown=%d shut=%d self=%d funds=%d" % (dup, unk, shutc, selfc, fundsc))
    lines.append("total: %d" % total)
    for i in range(limit):
        t = tops[i]
        lines.append("top: %d %s %d" % (t[1], t[2], t[3]))
    lines.append("digest: %d" % g)

    sys.stdout.write('\n'.join(lines) + '\n')
    sys.exit(0)


main()
