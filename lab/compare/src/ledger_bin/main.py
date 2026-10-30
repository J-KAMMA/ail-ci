import sys


class Err(Exception):
    def __init__(self, kind):
        self.kind = kind


def parse(data):
    n = len(data)
    if n < 6 or data[0:4] != b"\xc7LXF" or data[4] != 2 or data[5] not in (0, 1):
        return None, "header", 0
    strict = data[5] == 1
    pos = 6
    recs = []
    while pos < n:
        start = pos
        try:
            op = data[pos]
            if op < 1 or op > 5:
                raise Err("opcode")
            pos += 1

            def rv():
                nonlocal pos
                val = 0
                shift = 0
                for i in range(5):
                    if pos >= n:
                        raise Err("truncated")
                    b = data[pos]
                    pos += 1
                    if i == 4 and b & 0x80:
                        raise Err("varint")
                    val |= (b & 0x7F) << shift
                    shift += 7
                    if not b & 0x80:
                        if i >= 1 and b == 0:
                            raise Err("varint")
                        if val > 0xFFFFFFFF:
                            raise Err("varint")
                        return val
                raise Err("varint")

            if op == 1:
                i = rv()
                if pos >= n:
                    raise Err("truncated")
                ln = data[pos]
                pos += 1
                if ln < 1 or ln > 32:
                    raise Err("name")
                for _ in range(ln):
                    if pos >= n:
                        raise Err("truncated")
                    b = data[pos]
                    pos += 1
                    if b < 0x21 or b > 0x7E:
                        raise Err("name")
                name = data[pos - ln:pos].decode("ascii")
                ini = rv()
                rec = (1, i, name, ini)
            elif op == 2:
                a = rv()
                b = rv()
                c = rv()
                rec = (2, a, b, c)
            elif op == 3:
                rec = (3, rv())
            elif op == 4:
                a = rv()
                b = rv()
                rec = (4, a, b)
            else:
                ln = rv()
                if n - pos < ln:
                    raise Err("truncated")
                pos += ln
                rec = (5,)
            if pos >= n:
                raise Err("truncated")
            c = 0
            for b in data[start:pos]:
                c = (c * 31 + b) % 251
            if data[pos] != c:
                raise Err("check")
            pos += 1
        except Err as e:
            return None, e.kind, start
        recs.append((start, rec))
    return (strict, recs), None, 0


def main():
    if len(sys.argv) != 2:
        sys.exit(1)
    try:
        with open(sys.argv[1], "rb") as f:
            data = f.read()
    except OSError:
        sys.exit(1)
    res, kind, off = parse(data)
    if res is None:
        print("error at offset %d: %s" % (off, kind))
        sys.exit(2)
    strict, recs = res
    acc = {}  # id -> [name, balance, open]
    rej = {"dup": 0, "unknown": 0, "shut": 0, "self": 0, "funds": 0}
    for off, r in recs:
        op = r[0]
        reason = None
        if op == 1:
            if r[1] in acc:
                reason = "dup"
            else:
                acc[r[1]] = [r[2], r[3], True]
        elif op == 2:
            f = acc.get(r[1])
            t = acc.get(r[2])
            if f is None or t is None:
                reason = "unknown"
            elif not f[2] or not t[2]:
                reason = "shut"
            elif r[1] == r[2]:
                reason = "self"
            elif r[3] > f[1]:
                reason = "funds"
            else:
                f[1] -= r[3]
                t[1] += r[3]
        elif op == 3:
            a = acc.get(r[1])
            if a is None:
                reason = "unknown"
            elif not a[2]:
                reason = "shut"
            else:
                a[2] = False
        elif op == 4:
            a = acc.get(r[1])
            if a is None:
                reason = "unknown"
            elif not a[2]:
                reason = "shut"
            else:
                a[1] += r[2]
        if reason:
            if strict:
                print("rejected at offset %d: %s" % (off, reason))
                sys.exit(3)
            rej[reason] += 1
    opn = sum(1 for a in acc.values() if a[2])
    out = []
    out.append("records: %d" % len(recs))
    out.append("accounts: %d open, %d shut" % (opn, len(acc) - opn))
    out.append("rejected: dup=%d unknown=%d shut=%d self=%d funds=%d" % (
        rej["dup"], rej["unknown"], rej["shut"], rej["self"], rej["funds"]))
    out.append("total: %d" % sum(a[1] for a in acc.values()))
    top = sorted(((i, a) for i, a in acc.items() if a[2]), key=lambda x: (-x[1][1], x[0]))[:5]
    for i, a in top:
        out.append("top: %d %s %d" % (i, a[0], a[1]))
    g = 0
    for i in sorted(acc):
        g = (g * 1000003 + i * 7 + acc[i][1]) % 1000000007
    out.append("digest: %d" % g)
    sys.stdout.write("\n".join(out) + "\n")


main()
