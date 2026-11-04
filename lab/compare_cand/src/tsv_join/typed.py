from ail import read_stdin_bytes, write_stdout_bytes
import sys


class St:

    def __init__(self, uidx: dict[int, int], uid: list[int], uname: list[str], uctry: list[str], uamt: list[int], unum: list[int], cidx: dict[str, int], cname: list[str], camt: list[int], cnum: list[int], good_users: int, good_orders: int, bad: int, unmatched: int):
        self.uidx = uidx
        self.uid = uid
        self.uname = uname
        self.uctry = uctry
        self.uamt = uamt
        self.unum = unum
        self.cidx = cidx
        self.cname = cname
        self.camt = camt
        self.cnum = cnum
        self.good_users = good_users
        self.good_orders = good_orders
        self.bad = bad
        self.unmatched = unmatched


def name_ok(data: bytes, a: int, b: int) -> bool:
    n = b - a
    if n < 1 or n > 24:
        return False
    i = a
    while i < b:
        c = data[i]
        if c >= 65 and c <= 90:
            i += 1
        elif c >= 97 and c <= 122:
            i += 1
        elif c >= 48 and c <= 57:
            i += 1
        elif c == 32 or c == 46 or c == 95 or c == 45:
            i += 1
        else:
            return False
    return True


def country_ok(data: bytes, a: int, b: int) -> bool:
    if b - a != 2:
        return False
    return 65 <= data[a] <= 90 and 65 <= data[a + 1] <= 90


def num(data: bytes, a: int, b: int, lo: int, hi: int) -> int:
    if a >= b:
        return -1
    v = 0
    i = a
    while i < b:
        c = data[i]
        if c < 48 or c > 57:
            return -1
        if v <= hi:
            v = v * 10 + (c - 48)
        i += 1
    if v < lo or v > hi:
        return -1
    return v


def is_users(data: bytes, a: int, b: int) -> bool:
    return (b - a == 6 and data[a] == 35 and data[a + 1] == 117 and data[a + 2] == 115
            and data[a + 3] == 101 and data[a + 4] == 114 and data[a + 5] == 115)


def is_orders(data: bytes, a: int, b: int) -> bool:
    return (b - a == 7 and data[a] == 35 and data[a + 1] == 111 and data[a + 2] == 114
            and data[a + 3] == 100 and data[a + 4] == 101 and data[a + 5] == 114 and data[a + 6] == 115)


def main() -> int:
    data = read_stdin_bytes(1 << 30)
    n = len(data)
    if n == 0:
        write_stdout_bytes(b"users 0 orders 0 bad 0 unmatched 0\ntotal 0\n")
        return 0
    st = St({}, [], [], [], [], [], {}, [], [], [], 0, 0, 0, 0)
    section = 0
    found_users = False
    found_orders = False
    pos = 0
    while pos < n:
        e = pos
        while e < n and data[e] != 10:
            e += 1
        t1 = pos
        while t1 < e and data[t1] != 9:
            t1 += 1
        t2 = t1 + 1
        while t2 < e and data[t2] != 9:
            t2 += 1
        t3 = t2 + 1
        while t3 < e and data[t3] != 9:
            t3 += 1
        two = t1 < e and t2 < e and t3 >= e
        if section == 0 and is_users(data, pos, e):
            section = 1
            found_users = True
        elif section == 1 and is_orders(data, pos, e):
            section = 2
            found_orders = True
        elif section == 1:
            ok = two and t1 > pos and t2 > t1 + 1 and t2 + 1 < e
            if ok:
                uidv = num(data, pos, t1, 1, 2000000000)
                if uidv < 0 or not name_ok(data, t1 + 1, t2) or not country_ok(data, t2 + 1, e) or st.uidx.get(uidv, -1) >= 0:
                    ok = False
            if ok:
                st.uidx[uidv] = len(st.uid)
                st.uid.append(uidv)
                st.uname.append(data[t1 + 1:t2].decode())
                st.uctry.append(data[t2 + 1:e].decode())
                st.uamt.append(0)
                st.unum.append(0)
                st.good_users += 1
            else:
                st.bad += 1
        elif section == 2:
            ok = two and t1 > pos and t2 > t1 + 1 and t2 + 1 < e
            if ok:
                oid = num(data, pos, t1, 1, 2000000000)
                uidv = num(data, t1 + 1, t2, 1, 2000000000)
                amt = num(data, t2 + 1, e, 0, 100000000)
                if oid < 0 or uidv < 0 or amt < 0:
                    ok = False
            if ok:
                st.good_orders += 1
                ui = st.uidx.get(uidv, -1)
                if ui < 0:
                    st.unmatched += 1
                else:
                    st.uamt[ui] += amt
                    st.unum[ui] += 1
                    cc = st.uctry[ui]
                    ci = st.cidx.get(cc, -1)
                    if ci < 0:
                        ci = len(st.cname)
                        st.cidx[cc] = ci
                        st.cname.append(cc)
                        st.camt.append(0)
                        st.cnum.append(0)
                    st.camt[ci] += amt
                    st.cnum[ci] += 1
            else:
                st.bad += 1
        pos = e + 1
    if not found_users or not found_orders:
        write_stdout_bytes(b"users 0 orders 0 bad 0 unmatched 0\ntotal 0\n")
        return 0
    print(f'users {st.good_users} orders {st.good_orders} bad {st.bad} unmatched {st.unmatched}')
    cids = [i for i in range(len(st.cname))]
    cids.sort(key=lambda i: (-st.camt[i], st.cname[i]))
    for i in cids:
        print(f'country {st.cname[i]} orders {st.cnum[i]} amount {st.camt[i]}')
    uids = [i for i in range(len(st.uid))]
    keep = [i for i in uids if st.unum[i] > 0]
    keep.sort(key=lambda i: (-st.uamt[i], st.uid[i]))
    shown = 0
    for i in keep:
        if shown == 10:
            break
        print(f'user {st.uid[i]} {st.uname[i]} {st.uamt[i]}')
        shown += 1
    total = 0
    for i in range(len(st.uamt)):
        total += st.uamt[i]
    print(f'total {total}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
