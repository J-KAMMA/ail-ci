from ail import read_stdin_bytes, write_stdout_bytes
import sys

class St:

    def __init__(self, gidx: dict[str, int], greg: list[str], gprod: list[str], gqty: list[int], grev: list[int], ridx: dict[str, int], rname: list[str], rrev: list[int], good: int, bad: int):
        self.gidx = gidx
        self.greg = greg
        self.gprod = gprod
        self.gqty = gqty
        self.grev = grev
        self.ridx = ridx
        self.rname = rname
        self.rrev = rrev
        self.good = good
        self.bad = bad

def name_ok(f: bytes) -> bool:
    n = len(f)
    if n < 1 or n > 16:
        return False
    for i in range(n):
        c = f[i]
        if c >= 97 and c <= 122:
            continue
        if c >= 48 and c <= 57:
            continue
        if c == 95:
            continue
        return False
    return True

def num(f: bytes, allow_neg: bool) -> int:
    n = len(f)
    i = 0
    neg = False
    if allow_neg and n > 0 and f[0] == 45:
        neg = True
        i = 1
    if i >= n:
        return 100000001
    v = 0
    while i < n:
        c = f[i]
        if c < 48 or c > 57:
            return 100000001
        if v <= 10000001:
            v = v * 10 + (c - 48)
        i += 1
    if neg:
        return -v
    return v

def main() -> int:
    data = read_stdin_bytes(1 << 30)
    if len(data) == 0:
        write_stdout_bytes(b'rows 0 bad 0 groups 0\ntotal 0\n')
        return 0
    st = St({}, [], [], [], [], {}, [], [], 0, 0)
    n = len(data)
    pos = 0
    first = True
    while pos < n:
        e = data.find(b'\n', pos)
        if e < 0:
            e = n
        if first:
            first = False
        else:
            ok = True
            c1 = data.find(b',', pos)
            c2 = -1
            c3 = -1
            c4 = -1
            if c1 >= 0 and c1 < e:
                c2 = data.find(b',', c1 + 1)
            if c2 >= 0 and c2 < e:
                c3 = data.find(b',', c2 + 1)
            if c3 >= 0 and c3 < e:
                c4 = data.find(b',', c3 + 1)
            if c1 < 0 or c1 >= e or c2 < 0 or c2 >= e or c3 < 0 or c3 >= e:
                ok = False
            if c4 >= 0 and c4 < e:
                ok = False
            if ok:
                reg = data[pos:c1]
                prod = data[c1 + 1:c2]
                qf = data[c2 + 1:c3]
                pf = data[c3 + 1:e]
                if not name_ok(reg) or not name_ok(prod) or len(qf) == 0 or len(pf) == 0:
                    ok = False
                else:
                    qty = num(qf, True)
                    price = num(pf, False)
                    if qty < -1000 or qty > 1000 or price < 0 or price > 10000000:
                        ok = False
                    else:
                        rev = qty * price
                        r = reg.decode()
                        p = prod.decode()
                        key = r + ' ' + p
                        gid = st.gidx.get(key, -1)
                        if gid < 0:
                            gid = len(st.greg)
                            st.gidx[key] = gid
                            st.greg.append(r)
                            st.gprod.append(p)
                            st.gqty.append(0)
                            st.grev.append(0)
                        st.gqty[gid] += qty
                        st.grev[gid] += rev
                        rid = st.ridx.get(r, -1)
                        if rid < 0:
                            rid = len(st.rname)
                            st.ridx[r] = rid
                            st.rname.append(r)
                            st.rrev.append(0)
                        st.rrev[rid] += rev
                        st.good += 1
            if not ok:
                st.bad += 1
        if e >= n:
            pos = n
        else:
            pos = e + 1
    print(f'rows {st.good} bad {st.bad} groups {len(st.greg)}')
    ids = [i for i in range(len(st.greg))]
    ids.sort(key=lambda i: (-st.grev[i], st.greg[i], st.gprod[i]))
    shown = 0
    for i in ids:
        if shown == 10:
            break
        print(f'{st.greg[i]} {st.gprod[i]} {st.gqty[i]} {st.grev[i]}')
        shown += 1
    ri = [i for i in range(len(st.rname))]
    ri.sort(key=lambda i: st.rname[i])
    for i in ri:
        print(f'region {st.rname[i]} revenue {st.rrev[i]}')
    total = 0
    for i in range(len(st.grev)):
        total += st.grev[i]
    print(f'total {total}')
    return 0

if __name__ == '__main__':
    sys.exit(main())
