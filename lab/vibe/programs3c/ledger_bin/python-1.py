import sys


class LErr(Exception):
    def __init__(self, kind):
        super().__init__(kind)
        self.kind = kind


def read_var(data, pos):
    value = 0
    count = 0
    n = len(data)
    while True:
        if pos >= n:
            raise LErr('truncated')
        b = data[pos]
        pos += 1
        count += 1
        if count == 5 and (b & 0x80):
            raise LErr('varint')
        value |= (b & 0x7F) << (7 * (count - 1))
        if not (b & 0x80):
            break
    if count >= 2 and data[pos - 1] == 0:
        raise LErr('varint')
    if value > 4294967295:
        raise LErr('varint')
    return value, pos


def parse(data):
    n = len(data)
    recs = []
    pos = 6
    while pos < n:
        start = pos
        op = data[pos]
        pos += 1
        try:
            if op == 1:
                id_, pos = read_var(data, pos)
                if pos >= n:
                    raise LErr('truncated')
                nl = data[pos]
                pos += 1
                if nl < 1 or nl > 32:
                    raise LErr('name')
                name = bytearray()
                for _ in range(nl):
                    if pos >= n:
                        raise LErr('truncated')
                    b = data[pos]
                    pos += 1
                    if not (0x21 <= b <= 0x7E):
                        raise LErr('name')
                    name.append(b)
                init, pos = read_var(data, pos)
                fields = (id_, bytes(name).decode('ascii'), init)
            elif op == 2:
                a, pos = read_var(data, pos)
                b, pos = read_var(data, pos)
                amt, pos = read_var(data, pos)
                fields = (a, b, amt)
            elif op == 3:
                id_, pos = read_var(data, pos)
                fields = (id_,)
            elif op == 4:
                id_, pos = read_var(data, pos)
                amt, pos = read_var(data, pos)
                fields = (id_, amt)
            elif op == 5:
                ln, pos = read_var(data, pos)
                if n - pos < ln:
                    raise LErr('truncated')
                pos += ln
                fields = ()
            else:
                raise LErr('opcode')
            if pos >= n:
                raise LErr('truncated')
            c = 0
            for b in data[start:pos]:
                c = (c * 31 + b) % 251
            if data[pos] != c:
                raise LErr('check')
            pos += 1
        except LErr as e:
            return None, (start, e.kind)
        recs.append((start, op, fields))
    return recs, None


def main():
    if len(sys.argv) != 2:
        return 1
    try:
        with open(sys.argv[1], 'rb') as f:
            data = f.read()
    except OSError:
        return 1

    if len(data) < 6 or data[0:4] != b'\xC7LXF' or data[4] != 2 or data[5] not in (0, 1):
        sys.stdout.write("error at offset 0: header\n")
        return 2
    strict = (data[5] & 1) == 1

    recs, err = parse(data)
    if err is not None:
        sys.stdout.write("error at offset %d: %s\n" % (err[0], err[1]))
        return 2

    accounts = {}  # id -> [name, balance, shut]
    rej = {'dup': 0, 'unknown': 0, 'shut': 0, 'self': 0, 'funds': 0}

    for start, op, f in recs:
        reason = None
        if op == 1:
            id_, name, init = f
            if id_ in accounts:
                reason = 'dup'
            else:
                accounts[id_] = [name, init, False]
        elif op == 2:
            a, b, amt = f
            if a not in accounts or b not in accounts:
                reason = 'unknown'
            elif accounts[a][2] or accounts[b][2]:
                reason = 'shut'
            elif a == b:
                reason = 'self'
            elif amt > accounts[a][1]:
                reason = 'funds'
            else:
                accounts[a][1] -= amt
                accounts[b][1] += amt
        elif op == 3:
            id_ = f[0]
            if id_ not in accounts:
                reason = 'unknown'
            elif accounts[id_][2]:
                reason = 'shut'
            else:
                accounts[id_][2] = True
        elif op == 4:
            id_, amt = f
            if id_ not in accounts:
                reason = 'unknown'
            elif accounts[id_][2]:
                reason = 'shut'
            else:
                accounts[id_][1] += amt
        # op 5 (NOTE) never rejected, no effect

        if reason is not None:
            if strict:
                sys.stdout.write("rejected at offset %d: %s\n" % (start, reason))
                return 3
            rej[reason] += 1

    R = len(recs)
    open_n = sum(1 for a in accounts.values() if not a[2])
    shut_n = len(accounts) - open_n
    total = sum(a[1] for a in accounts.values())
    opened = [(id_, a[0], a[1]) for id_, a in accounts.items() if not a[2]]
    opened.sort(key=lambda t: (-t[2], t[0]))
    top = opened[:5]
    g = 0
    for id_ in sorted(accounts):
        g = (g * 1000003 + id_ * 7 + accounts[id_][1]) % 1000000007

    out = []
    out.append("records: %d\n" % R)
    out.append("accounts: %d open, %d shut\n" % (open_n, shut_n))
    out.append("rejected: dup=%d unknown=%d shut=%d self=%d funds=%d\n" % (
        rej['dup'], rej['unknown'], rej['shut'], rej['self'], rej['funds']))
    out.append("total: %d\n" % total)
    for id_, name, bal in top:
        out.append("top: %d %s %d\n" % (id_, name, bal))
    out.append("digest: %d\n" % g)
    sys.stdout.write("".join(out))
    return 0


if __name__ == "__main__":
    sys.exit(main())
