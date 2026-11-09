import sys


class Bad(Exception):
    def __init__(self, kind):
        super().__init__(kind)
        self.kind = kind


class Rej(Exception):
    def __init__(self, reason):
        super().__init__(reason)
        self.reason = reason


def main():
    if len(sys.argv) != 2:
        return 1
    try:
        with open(sys.argv[1], 'rb') as f:
            data = f.read()
    except Exception:
        return 1

    n = len(data)

    def fail(off, kind):
        sys.stdout.write(f"error at offset {off}: {kind}\n")
        return 2

    if n < 6 or data[0:4] != bytes([0xC7, 0x4C, 0x58, 0x46]) or data[4] != 2 or (data[5] & ~1):
        return fail(0, 'header')

    strict = data[5] & 1

    def read_var(p):
        val = 0
        for i in range(5):
            if p >= n:
                raise Bad('truncated')
            b = data[p]
            p += 1
            if i == 4 and (b & 0x80):
                raise Bad('varint')
            val |= (b & 0x7F) << (7 * i)
            if not (b & 0x80):
                if i >= 1 and b == 0:
                    raise Bad('varint')
                if val > 0xFFFFFFFF:
                    raise Bad('varint')
                return val, p
        raise Bad('varint')

    def read_name(p):
        if p >= n:
            raise Bad('truncated')
        ln = data[p]
        p += 1
        if ln < 1 or ln > 32:
            raise Bad('name')
        name = bytearray()
        for _ in range(ln):
            if p >= n:
                raise Bad('truncated')
            b = data[p]
            p += 1
            if not (0x21 <= b <= 0x7E):
                raise Bad('name')
            name.append(b)
        return name.decode('ascii'), p

    def parse(start):
        op = data[start]
        p = start + 1
        if op == 1:
            acc, p = read_var(p)
            name, p = read_name(p)
            init, p = read_var(p)
            fields = (acc, name, init)
        elif op == 2:
            a, p = read_var(p)
            b, p = read_var(p)
            amt, p = read_var(p)
            fields = (a, b, amt)
        elif op == 3:
            a, p = read_var(p)
            fields = (a,)
        elif op == 4:
            a, p = read_var(p)
            amt, p = read_var(p)
            fields = (a, amt)
        else:
            ln, p = read_var(p)
            if n - p < ln:
                raise Bad('truncated')
            p += ln
            fields = ()
        if p >= n:
            raise Bad('truncated')
        c = 0
        for b in data[start:p]:
            c = (c * 31 + b) % 251
        if data[p] != c:
            raise Bad('check')
        p += 1
        return op, fields, p

    records = []
    pos = 6
    cur = 6
    try:
        while pos < n:
            cur = pos
            if data[pos] not in (1, 2, 3, 4, 5):
                raise Bad('opcode')
            op, fields, pos = parse(cur)
            records.append((cur, op, fields))
    except Bad as e:
        return fail(cur, e.kind)

    accts = {}  # id -> [name, balance, shut]
    rej = {'dup': 0, 'unknown': 0, 'shut': 0, 'self': 0, 'funds': 0}

    for start, op, f in records:
        try:
            if op == 1:
                aid, name, init = f
                if aid in accts:
                    raise Rej('dup')
                accts[aid] = [name, init, False]
            elif op == 2:
                a, b, amt = f
                if a not in accts or b not in accts:
                    raise Rej('unknown')
                if accts[a][2] or accts[b][2]:
                    raise Rej('shut')
                if a == b:
                    raise Rej('self')
                if amt > accts[a][1]:
                    raise Rej('funds')
                accts[a][1] -= amt
                accts[b][1] += amt
            elif op == 3:
                (aid,) = f
                if aid not in accts:
                    raise Rej('unknown')
                if accts[aid][2]:
                    raise Rej('shut')
                accts[aid][2] = True
            elif op == 4:
                aid, amt = f
                if aid not in accts:
                    raise Rej('unknown')
                if accts[aid][2]:
                    raise Rej('shut')
                accts[aid][1] += amt
            # NOTE: never rejected, no effect
        except Rej as e:
            if strict:
                sys.stdout.write(f"rejected at offset {start}: {e.reason}\n")
                return 3
            rej[e.reason] += 1

    open_count = sum(1 for v in accts.values() if not v[2])
    shut_count = len(accts) - open_count
    total = sum(v[1] for v in accts.values())

    opens = sorted((-v[1], aid, v[0]) for aid, v in accts.items() if not v[2])
    top = opens[:5]

    g = 0
    for aid in sorted(accts):
        g = (g * 1000003 + aid * 7 + accts[aid][1]) % 1000000007

    out = []
    out.append(f"records: {len(records)}\n")
    out.append(f"accounts: {open_count} open, {shut_count} shut\n")
    out.append(f"rejected: dup={rej['dup']} unknown={rej['unknown']} shut={rej['shut']} "
               f"self={rej['self']} funds={rej['funds']}\n")
    out.append(f"total: {total}\n")
    for negbal, aid, name in top:
        out.append(f"top: {aid} {name} {-negbal}\n")
    out.append(f"digest: {g}\n")
    sys.stdout.write("".join(out))
    return 0


if __name__ == "__main__":
    sys.exit(main())
