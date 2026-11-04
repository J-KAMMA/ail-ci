import sys


def name_ok(data, a, b):
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


def country_ok(data, a, b):
    if b - a != 2:
        return False
    return 65 <= data[a] <= 90 and 65 <= data[a + 1] <= 90


def number(data, a, b, lo, hi):
    if a >= b:
        return None
    v = 0
    i = a
    while i < b:
        c = data[i]
        if c < 48 or c > 57:
            return None
        if v <= hi:
            v = v * 10 + (c - 48)
        i += 1
    if v < lo or v > hi:
        return None
    return v


def is_users(data, a, b):
    return (b - a == 6 and data[a] == 35 and data[a + 1] == 117 and data[a + 2] == 115
            and data[a + 3] == 101 and data[a + 4] == 114 and data[a + 5] == 115)


def is_orders(data, a, b):
    return (b - a == 7 and data[a] == 35 and data[a + 1] == 111 and data[a + 2] == 114
            and data[a + 3] == 100 and data[a + 4] == 101 and data[a + 5] == 114 and data[a + 6] == 115)


def fields(data, pos, e):
    t1 = pos
    while t1 < e and data[t1] != 9:
        t1 += 1
    if t1 >= e:
        return None
    t2 = t1 + 1
    while t2 < e and data[t2] != 9:
        t2 += 1
    if t2 >= e:
        return None
    t3 = t2 + 1
    while t3 < e and data[t3] != 9:
        t3 += 1
    if t3 < e:
        return None
    return t1, t2


def main():
    data = sys.stdin.buffer.read()
    n = len(data)
    if n == 0:
        sys.stdout.write("users 0 orders 0 bad 0 unmatched 0\ntotal 0\n")
        return
    uname = {}
    uctry = {}
    uamt = {}
    unum = {}
    camt = {}
    cnum = {}
    good_users = 0
    good_orders = 0
    bad = 0
    unmatched = 0
    section = 0
    found_users = False
    found_orders = False
    pos = 0
    while pos < n:
        e = pos
        while e < n and data[e] != 10:
            e += 1
        f = fields(data, pos, e)
        if section == 0 and is_users(data, pos, e):
            section = 1
            found_users = True
        elif section == 1 and is_orders(data, pos, e):
            section = 2
            found_orders = True
        elif section == 1:
            ok = f is not None
            if ok:
                t1, t2 = f
                if t1 == pos or t2 == t1 + 1 or t2 + 1 >= e:
                    ok = False
            if ok:
                uid = number(data, pos, t1, 1, 2000000000)
                if uid is None or not name_ok(data, t1 + 1, t2) or not country_ok(data, t2 + 1, e) or uid in uname:
                    ok = False
            if ok:
                uname[uid] = data[t1 + 1:t2]
                uctry[uid] = data[t2 + 1:e]
                good_users += 1
            else:
                bad += 1
        elif section == 2:
            ok = f is not None
            if ok:
                t1, t2 = f
                if t1 == pos or t2 == t1 + 1 or t2 + 1 >= e:
                    ok = False
            if ok:
                oid = number(data, pos, t1, 1, 2000000000)
                uid = number(data, t1 + 1, t2, 1, 2000000000)
                amt = number(data, t2 + 1, e, 0, 100000000)
                if oid is None or uid is None or amt is None:
                    ok = False
            if ok:
                good_orders += 1
                if uid in uname:
                    uamt[uid] = uamt.get(uid, 0) + amt
                    unum[uid] = unum.get(uid, 0) + 1
                    cc = uctry[uid]
                    camt[cc] = camt.get(cc, 0) + amt
                    cnum[cc] = cnum.get(cc, 0) + 1
                else:
                    unmatched += 1
            else:
                bad += 1
        pos = e + 1
    if not found_users or not found_orders:
        sys.stdout.write("users 0 orders 0 bad 0 unmatched 0\ntotal 0\n")
        return
    out = ["users %d orders %d bad %d unmatched %d" % (good_users, good_orders, bad, unmatched)]
    for cc in sorted(camt, key=lambda c: (-camt[c], c)):
        out.append("country %s orders %d amount %d" % (cc.decode(), cnum[cc], camt[cc]))
    order = sorted(uamt, key=lambda u: (-uamt[u], u))
    for uid in order[:10]:
        out.append("user %d %s %d" % (uid, uname[uid].decode(), uamt[uid]))
    out.append("total %d" % sum(uamt.values()))
    sys.stdout.write("\n".join(out) + "\n")


main()
