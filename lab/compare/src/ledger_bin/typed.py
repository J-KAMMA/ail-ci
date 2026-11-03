from ail import read_bytes
import sys

class Rd:

    def __init__(self, data: bytes, pos: int, err: int):
        self.data = data
        self.pos = pos
        self.err = err

def readvar(r: Rd) -> int:
    v = 0
    n = 0
    last = 0
    while True:
        if r.pos >= len(r.data):
            r.err = 1
            return 0
        b = r.data[r.pos]
        r.pos += 1
        n += 1
        last = b & 127
        v += last << 7 * (n - 1)
        if b & 128 == 0:
            break
        if n == 5:
            r.err = 2
            return 0
    if n >= 2 and last == 0:
        r.err = 2
        return 0
    if v > 4294967295:
        r.err = 2
        return 0
    return v

def kindname(e: int) -> str:
    if e == 1:
        return 'truncated'
    if e == 2:
        return 'varint'
    if e == 3:
        return 'name'
    if e == 4:
        return 'check'
    return 'opcode'

def main() -> int:
    if len(sys.argv) != 2:
        return 1
    data = b''
    try:
        data = read_bytes(sys.argv[1])
    except OSError as e1:
        return 1
    n = len(data)
    if n < 6 or data[0] != 199 or data[1] != 76 or (data[2] != 88) or (data[3] != 70) or (data[4] != 2) or (data[5] > 1):
        print('error at offset 0: header')
        return 2
    strict = data[5] == 1
    r = Rd(data, 6, 0)
    ops: list[int] = []
    xs: list[int] = []
    ys: list[int] = []
    zs: list[int] = []
    offs: list[int] = []
    rnames: list[str] = []
    while r.pos < n:
        start = r.pos
        op = data[start]
        r.pos += 1
        x = 0
        y = 0
        z = 0
        if op == 1:
            x = readvar(r)
            if r.err == 0:
                if r.pos >= n:
                    r.err = 1
                else:
                    nl = data[r.pos]
                    r.pos += 1
                    if nl < 1 or nl > 32:
                        r.err = 3
                    else:
                        k = 0
                        while k < nl and r.err == 0:
                            if r.pos >= n:
                                r.err = 1
                            else:
                                c = data[r.pos]
                                r.pos += 1
                                if c < 33 or c > 126:
                                    r.err = 3
                            k += 1
                        if r.err == 0:
                            y = len(rnames)
                            rnames.append(data[r.pos - nl:r.pos].decode())
                            z = readvar(r)
        elif op == 2:
            x = readvar(r)
            if r.err == 0:
                y = readvar(r)
            if r.err == 0:
                z = readvar(r)
        elif op == 3:
            x = readvar(r)
        elif op == 4:
            x = readvar(r)
            if r.err == 0:
                y = readvar(r)
        elif op == 5:
            x = readvar(r)
            if r.err == 0:
                if n - r.pos < x:
                    r.err = 1
                else:
                    r.pos += x
        else:
            r.err = 5
        if r.err == 0:
            if r.pos >= n:
                r.err = 1
            else:
                c = 0
                i = start
                while i < r.pos:
                    c = (c * 31 + data[i]) % 251
                    i += 1
                if data[r.pos] != c:
                    r.err = 4
                r.pos += 1
        if r.err != 0:
            print(f'error at offset {start}: {kindname(r.err)}')
            return 2
        ops.append(op)
        xs.append(x)
        ys.append(y)
        zs.append(z)
        offs.append(start)
    idx: dict[int, int] = {}
    ids: list[int] = []
    names: list[str] = []
    bal: list[int] = []
    shut: list[int] = []
    rej = [0, 0, 0, 0, 0]
    i = 0
    while i < len(ops):
        op = ops[i]
        why = -1
        if op == 1:
            if xs[i] in idx:
                why = 0
            else:
                idx[xs[i]] = len(ids)
                ids.append(xs[i])
                names.append(rnames[ys[i]])
                bal.append(zs[i])
                shut.append(0)
        elif op == 2:
            f = xs[i]
            t = ys[i]
            if f not in idx:
                why = 1
            elif t not in idx:
                why = 1
            elif shut[idx[f]] == 1:
                why = 2
            elif shut[idx[t]] == 1:
                why = 2
            elif f == t:
                why = 3
            elif zs[i] > bal[idx[f]]:
                why = 4
            else:
                bal[idx[f]] -= zs[i]
                bal[idx[t]] += zs[i]
        elif op == 3:
            if xs[i] not in idx:
                why = 1
            elif shut[idx[xs[i]]] == 1:
                why = 2
            else:
                shut[idx[xs[i]]] = 1
        elif op == 4:
            if xs[i] not in idx:
                why = 1
            elif shut[idx[xs[i]]] == 1:
                why = 2
            else:
                bal[idx[xs[i]]] += ys[i]
        if why >= 0:
            if strict:
                rs = ['dup', 'unknown', 'shut', 'self', 'funds']
                print(f'rejected at offset {offs[i]}: {rs[why]}')
                return 3
            rej[why] += 1
        i += 1
    nopen = 0
    nshut = 0
    total = 0
    k = 0
    while k < len(ids):
        if shut[k] == 1:
            nshut += 1
        else:
            nopen += 1
        total += bal[k]
        k += 1
    ord_ids: list[int] = [j for j in range(len(ids))]
    ord_ids.sort(key=lambda j: ids[j])
    g = 0
    for j in ord_ids:
        g = (g * 1000003 + ids[j] * 7 + bal[j]) % 1000000007
    cand: list[int] = [j for j in range(len(ids)) if shut[j] == 0]
    cand.sort(key=lambda j: (-bal[j], ids[j]))
    print(f'records: {len(ops)}')
    print(f'accounts: {nopen} open, {nshut} shut')
    print(f'rejected: dup={rej[0]} unknown={rej[1]} shut={rej[2]} self={rej[3]} funds={rej[4]}')
    print(f'total: {total}')
    m = 0
    for j in cand:
        if m < 5:
            print(f'top: {ids[j]} {names[j]} {bal[j]}')
        m += 1
    print(f'digest: {g}')
    return 0

if __name__ == "__main__":
    sys.exit(main())
