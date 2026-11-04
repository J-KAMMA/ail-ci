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

def name_ok(data: bytes, a: int, b: int) -> bool:
    n = b - a
    if n < 1 or n > 16:
        return False
    i = a
    while i < b:
        c = data[i]
        if c >= 97 and c <= 122:
            i += 1
            continue
        if c >= 48 and c <= 57:
            i += 1
            continue
        if c == 95:
            i += 1
            continue
        return False
    return True

def num(data: bytes, a: int, b: int, allow_neg: bool) -> int:
    i = a
    neg = False
    if allow_neg and i < b and data[i] == 45:
        neg = True
        i += 1
    if i >= b:
        return 100000001
    v = 0
    while i < b:
        c = data[i]
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
    n = len(data)
    if n == 0:
        write_stdout_bytes(b'rows 0 bad 0 groups 0\ntotal 0\n')
        return 0
    st = St({}, [], [], [], [], {}, [], [], 0, 0)
    pos = 0
    while pos < n and data[pos] != 10:
        pos += 1
    if pos < n:
        pos += 1
    while pos < n:
        e = pos
        while e < n and data[e] != 10:
            e += 1
        c1 = pos
        while c1 < e and data[c1] != 44:
            c1 += 1
        c2 = c1 + 1
        while c2 < e and data[c2] != 44:
            c2 += 1
        c3 = c2 + 1
        while c3 < e and data[c3] != 44:
            c3 += 1
        ok = c1 < e and c2 < e and c3 < e
        if ok:
            c4 = c3 + 1
            while c4 < e and data[c4] != 44:
                c4 += 1
            if c4 < e:
                ok = False
        if ok:
            if not name_ok(data, pos, c1) or not name_ok(data, c1 + 1, c2) or c2 + 1 >= c3 or c3 + 1 >= e:
                ok = False
            else:
                qty = num(data, c2 + 1, c3, True)
                price = num(data, c3 + 1, e, False)
                if qty < -1000 or qty > 1000 or price < 0 or price > 10000000:
                    ok = False
                else:
                    rev = qty * price
                    r = data[pos:c1].decode()
                    p = data[c1 + 1:c2].decode()
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
