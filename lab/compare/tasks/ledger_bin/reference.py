"""Reference implementation of ledger_bin (see spec.md): reference.py FILE

One pass: structure is checked while the ledger is replayed; the replay result is only printed if
the whole file turns out to be structurally valid.
"""
import sys
from operator import mul

MAGIC = b'\xc7LXF\x02'
POWERS = {}


def powers(n):
    """[31^(n-1), ..., 31^1, 31^0] mod 251."""
    p = [1] * n
    for i in range(n - 2, -1, -1):
        p[i] = p[i + 1] * 31 % 251
    return p


class Structural(Exception):
    def __init__(self, offset, kind):
        self.offset = offset
        self.kind = kind


def main(argv):
    if len(argv) != 2:
        return 1
    try:
        with open(argv[1], 'rb') as f:
            data = f.read()
    except OSError:
        return 1
    out = sys.stdout
    if len(data) < 6 or data[:5] != MAGIC or data[5] not in (0, 1):
        out.write('error at offset 0: header\n')
        return 2
    strict = data[5] == 1
    n = len(data)
    pos = 6
    records = 0
    bal = {}        # id -> balance
    names = {}      # id -> name (bytes)
    shut = set()
    rej = {'dup': 0, 'unknown': 0, 'shut': 0, 'self': 0, 'funds': 0}
    first_rej = None

    def var(p, start):
        # returns (value, new_pos)
        v = 0
        shift = 0
        k = 0
        while True:
            if p >= n:
                raise Structural(start, 'truncated')
            b = data[p]
            p += 1
            k += 1
            if k == 5 and b & 0x80:
                raise Structural(start, 'varint')
            v |= (b & 0x7f) << shift
            shift += 7
            if not b & 0x80:
                break
        if (k > 1 and b == 0) or v > 0xFFFFFFFF:
            raise Structural(start, 'varint')
        return v, p

    try:
        while pos < n:
            start = pos
            op = data[pos]
            pos += 1
            if op == 2:
                # fast path for single-byte varints is inside var(); keep the generic code simple
                a, pos = var(pos, start)
                b, pos = var(pos, start)
                amt, pos = var(pos, start)
                fields = (a, b, amt)
            elif op == 1:
                ident, pos = var(pos, start)
                if pos >= n:
                    raise Structural(start, 'truncated')
                ln = data[pos]
                pos += 1
                if ln < 1 or ln > 32:
                    raise Structural(start, 'name')
                for q in range(pos, pos + ln):
                    if q >= n:
                        raise Structural(start, 'truncated')
                    if not 0x21 <= data[q] <= 0x7e:
                        raise Structural(start, 'name')
                name = data[pos:pos + ln]
                pos += ln
                init, pos = var(pos, start)
                fields = (ident, name, init)
            elif op == 3:
                ident, pos = var(pos, start)
                fields = (ident,)
            elif op == 4:
                ident, pos = var(pos, start)
                amt, pos = var(pos, start)
                fields = (ident, amt)
            elif op == 5:
                ln, pos = var(pos, start)
                if n - pos < ln:
                    raise Structural(start, 'truncated')
                pos += ln
                fields = ()
            else:
                raise Structural(start, 'opcode')
            if pos >= n:
                raise Structural(start, 'truncated')
            # c = (c * 31 + b) mod 251 over the record bytes equals sum(b_k * 31^(L-1-k)) mod 251
            ln = pos - start
            pw = POWERS.get(ln)
            if pw is None:
                pw = POWERS[ln] = powers(ln)
            c = sum(map(mul, data[start:pos], pw)) % 251
            if data[pos] != c:
                raise Structural(start, 'check')
            pos += 1
            records += 1
            # replay
            reason = None
            if op == 2:
                a, b, amt = fields
                if a not in bal or b not in bal:
                    reason = 'unknown'
                elif a in shut or b in shut:
                    reason = 'shut'
                elif a == b:
                    reason = 'self'
                elif amt > bal[a]:
                    reason = 'funds'
                else:
                    bal[a] -= amt
                    bal[b] += amt
            elif op == 1:
                ident, name, init = fields
                if ident in bal:
                    reason = 'dup'
                else:
                    bal[ident] = init
                    names[ident] = name
            elif op == 3:
                ident = fields[0]
                if ident not in bal:
                    reason = 'unknown'
                elif ident in shut:
                    reason = 'shut'
                else:
                    shut.add(ident)
            elif op == 4:
                ident, amt = fields
                if ident not in bal:
                    reason = 'unknown'
                elif ident in shut:
                    reason = 'shut'
                else:
                    bal[ident] += amt
            if reason is not None:
                rej[reason] += 1
                if first_rej is None:
                    first_rej = (start, reason)
    except Structural as e:
        out.write('error at offset %d: %s\n' % (e.offset, e.kind))
        return 2
    if strict and first_rej is not None:
        out.write('rejected at offset %d: %s\n' % first_rej)
        return 3
    lines = ['records: %d' % records,
             'accounts: %d open, %d shut' % (len(bal) - len(shut), len(shut)),
             'rejected: dup=%d unknown=%d shut=%d self=%d funds=%d' % (
                 rej['dup'], rej['unknown'], rej['shut'], rej['self'], rej['funds']),
             'total: %d' % sum(bal.values())]
    top = sorted((-v, k) for k, v in bal.items() if k not in shut)[:5]
    for negv, k in top:
        lines.append('top: %d %s %d' % (k, names[k].decode('ascii'), -negv))
    g = 0
    for k in sorted(bal):
        g = (g * 1000003 + k * 7 + bal[k]) % 1000000007
    lines.append('digest: %d' % g)
    out.write('\n'.join(lines) + '\n')
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv))
