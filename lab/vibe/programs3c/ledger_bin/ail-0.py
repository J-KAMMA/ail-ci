import sys


class Err(Exception):
    def __init__(self, off, kind):
        self.off = off
        self.kind = kind


def read_var(data, pos, start):
    n = len(data)
    val = 0
    i = 0
    while True:
        if pos >= n:
            raise Err(start, 'truncated')
        b = data[pos]
        pos += 1
        if i == 4 and (b & 0x80):
            raise Err(start, 'varint')
        val |= (b & 0x7F) << (7 * i)
        if not (b & 0x80):
            break
        i += 1
    if i >= 1 and data[pos - 1] == 0:
        raise Err(start, 'varint')
    if val > 4294967295:
        raise Err(start, 'varint')
    return val, pos


def parse(data):
    n = len(data)
    pos = 6
    recs = []
    while pos < n:
        start = pos
        op = data[pos]
        pos += 1
        if op < 1 or op > 5:
            raise Err(start, 'opcode')
        fields = None
        if op == 1:
            aid, pos = read_var(data, pos, start)
            if pos >= n:
                raise Err(start, 'truncated')
            nl = data[pos]
            pos += 1
            if nl < 1 or nl > 32:
                raise Err(start, 'name')
            name = bytearray()
            for _ in range(nl):
                if pos >= n:
                    raise Err(start, 'truncated')
                b = data[pos]
                pos += 1
                if b < 0x21 or b > 0x7E:
                    raise Err(start, 'name')
                name.append(b)
            init, pos = read_var(data, pos, start)
            fields = (aid, bytes(name), init)
        elif op == 2:
            a, pos = read_var(data, pos, start)
            b, pos = read_var(data, pos, start)
            amt, pos = read_var(data, pos, start)
            fields = (a, b, amt)
        elif op == 3:
            aid, pos = read_var(data, pos, start)
            fields = (aid,)
        elif op == 4:
            aid, pos = read_var(data, pos, start)
            amt, pos = read_var(data, pos, start)
            fields = (aid, amt)
        else:
            ln, pos = read_var(data, pos, start)
            if n - pos < ln:
                raise Err(start, 'truncated')
            pos += ln
            fields = None
        if pos >= n:
            raise Err(start, 'truncated')
        c = 0
        for k in range(start, pos):
            c = (c * 31 + data[k]) % 251
        if data[pos] != c:
            raise Err(start, 'check')
        pos += 1
        recs.append((start, op, fields))
    return recs


def main():
    if len(sys.argv) != 2:
        sys.exit(1)
    try:
        with open(sys.argv[1], 'rb') as f:
            data = f.read()
    except Exception:
        sys.exit(1)

    try:
        n = len(data)
        if n < 6 or data[0] != 0xC7 or data[1] != 0x4C or data[2] != 0x58 \
                or data[3] != 0x46 or data[4] != 2 or data[5] not in (0, 1):
            raise Err(0, 'header')
        strict = (data[5] & 1) == 1
        recs = parse(data)
    except Err as e:
        sys.stdout.write("error at offset %d: %s\n" % (e.off, e.kind))
        sys.exit(2)

    accts = {}
    rej = {'dup': 0, 'unknown': 0, 'shut': 0, 'self': 0, 'funds': 0}

    for start, op, f in recs:
        reason = None
        if op == 1:
            aid, name, init = f
            if aid in accts:
                reason = 'dup'
            else:
                accts[aid] = [name, init, False]
        elif op == 2:
            a, b, amt = f
            if a not in accts or b not in accts:
                reason = 'unknown'
            elif accts[a][2] or accts[b][2]:
                reason = 'shut'
            elif a == b:
                reason = 'self'
            elif amt > accts[a][1]:
                reason = 'funds'
            else:
                accts[a][1] -= amt
                accts[b][1] += amt
        elif op == 3:
            aid = f[0]
            if aid not in accts:
                reason = 'unknown'
            elif accts[aid][2]:
                reason = 'shut'
            else:
                accts[aid][2] = True
        elif op == 4:
            aid, amt = f
            if aid not in accts:
                reason = 'unknown'
            elif accts[aid][2]:
                reason = 'shut'
            else:
                accts[aid][1] += amt
        if reason is not None:
            if strict:
                sys.stdout.write("rejected at offset %d: %s\n" % (start, reason))
                sys.exit(3)
            rej[reason] += 1

    R = len(recs)
    open_ids = [k for k in accts if not accts[k][2]]
    A = len(open_ids)
    S = len(accts) - A
    T = 0
    for k in accts:
        T += accts[k][1]
    top = sorted(open_ids, key=lambda k: (-accts[k][1], k))[:5]
    g = 0
    for k in sorted(accts):
        g = (g * 1000003 + k * 7 + accts[k][1]) % 1000000007

    out = []
    out.append("records: %d\n" % R)
    out.append("accounts: %d open, %d shut\n" % (A, S))
    out.append("rejected: dup=%d unknown=%d shut=%d self=%d funds=%d\n"
               % (rej['dup'], rej['unknown'], rej['shut'], rej['self'], rej['funds']))
    out.append("total: %d\n" % T)
    for k in top:
        out.append("top: %d %s %d\n" % (k, accts[k][0].decode('ascii'), accts[k][1]))
    out.append("digest: %d\n" % g)
    sys.stdout.write("".join(out))
    sys.exit(0)


main()
