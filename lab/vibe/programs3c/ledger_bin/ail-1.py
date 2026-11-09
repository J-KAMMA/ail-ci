import sys

HDR = bytes([0xC7, 0x4C, 0x58, 0x46])


class PErr(Exception):
    pass


def fail(kind):
    raise PErr(kind)


def err(off, kind):
    sys.stdout.write("error at offset " + str(off) + ": " + kind + "\n")
    sys.exit(2)


def main():
    if len(sys.argv) != 2:
        sys.exit(1)
    try:
        with open(sys.argv[1], 'rb') as fh:
            data = fh.read()
    except Exception:
        sys.exit(1)

    n = len(data)

    if n < 6 or data[0:4] != HDR or data[4] != 2 or data[5] not in (0, 1):
        err(0, 'header')

    strict = data[5] & 1

    def read_var(pos):
        val = 0
        shift = 0
        cnt = 0
        b = 0
        while True:
            if pos >= n:
                fail('truncated')
            b = data[pos]
            pos += 1
            cnt += 1
            if cnt == 5 and (b & 0x80):
                fail('varint')
            val |= (b & 0x7F) << shift
            shift += 7
            if not (b & 0x80):
                break
        if cnt >= 2 and b == 0:
            fail('varint')
        if val > 4294967295:
            fail('varint')
        return val, pos

    recs = []
    pos = 6
    while pos < n:
        X = pos
        try:
            op = data[pos]
            pos += 1
            if op < 1 or op > 5:
                fail('opcode')
            if op == 1:
                aid, pos = read_var(pos)
                if pos >= n:
                    fail('truncated')
                nl = data[pos]
                pos += 1
                if nl < 1 or nl > 32:
                    fail('name')
                s = pos
                for i in range(nl):
                    if pos >= n:
                        fail('truncated')
                    b = data[pos]
                    pos += 1
                    if b < 0x21 or b > 0x7E:
                        fail('name')
                name = data[s:pos].decode('ascii')
                init, pos = read_var(pos)
                fields = (aid, name, init)
            elif op == 2:
                f, pos = read_var(pos)
                t, pos = read_var(pos)
                a, pos = read_var(pos)
                fields = (f, t, a)
            elif op == 3:
                aid, pos = read_var(pos)
                fields = (aid,)
            elif op == 4:
                aid, pos = read_var(pos)
                a, pos = read_var(pos)
                fields = (aid, a)
            else:
                ln, pos = read_var(pos)
                if ln > n - pos:
                    fail('truncated')
                pos += ln
                fields = ()
            if pos >= n:
                fail('truncated')
            c = 0
            for b in data[X:pos]:
                c = (c * 31 + b) % 251
            if data[pos] != c:
                fail('check')
            pos += 1
        except PErr as e:
            err(X, e.args[0])
        recs.append((X, op, fields))

    accts = {}
    rej = {'dup': 0, 'unknown': 0, 'shut': 0, 'self': 0, 'funds': 0}

    for X, op, fl in recs:
        reason = ''
        if op == 1:
            aid, name, init = fl
            if aid in accts:
                reason = 'dup'
            else:
                accts[aid] = [name, init, False]
                continue
        elif op == 2:
            f, t, a = fl
            if f not in accts or t not in accts:
                reason = 'unknown'
            elif accts[f][2] or accts[t][2]:
                reason = 'shut'
            elif f == t:
                reason = 'self'
            elif a > accts[f][1]:
                reason = 'funds'
            else:
                accts[f][1] -= a
                accts[t][1] += a
                continue
        elif op == 3:
            aid = fl[0]
            if aid not in accts:
                reason = 'unknown'
            elif accts[aid][2]:
                reason = 'shut'
            else:
                accts[aid][2] = True
                continue
        elif op == 4:
            aid, a = fl
            if aid not in accts:
                reason = 'unknown'
            elif accts[aid][2]:
                reason = 'shut'
            else:
                accts[aid][1] += a
                continue
        else:
            continue

        if strict:
            sys.stdout.write("rejected at offset " + str(X) + ": " + reason + "\n")
            sys.exit(3)
        rej[reason] += 1

    R = len(recs)
    openc = 0
    T = 0
    openlist = []
    for k in accts:
        v = accts[k]
        T += v[1]
        if not v[2]:
            openc += 1
            openlist.append((-v[1], k, v[0]))
    shutc = len(accts) - openc
    openlist.sort()

    g = 0
    for k in sorted(accts):
        g = (g * 1000003 + k * 7 + accts[k][1]) % 1000000007

    out = []
    out.append("records: " + str(R) + "\n")
    out.append("accounts: " + str(openc) + " open, " + str(shutc) + " shut\n")
    out.append("rejected: dup=" + str(rej['dup']) + " unknown=" + str(rej['unknown'])
               + " shut=" + str(rej['shut']) + " self=" + str(rej['self'])
               + " funds=" + str(rej['funds']) + "\n")
    out.append("total: " + str(T) + "\n")
    for item in openlist[:5]:
        out.append("top: " + str(item[1]) + " " + item[2] + " " + str(-item[0]) + "\n")
    out.append("digest: " + str(g) + "\n")
    sys.stdout.write("".join(out))
    sys.exit(0)


main()
