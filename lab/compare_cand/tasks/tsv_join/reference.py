"""Reference implementation of tsv_join (see spec.md): reference.py < data.tsv"""
import sys

NAME_OK = frozenset(b'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789 ._-')


def name_ok(f):
    n = len(f)
    if n < 1 or n > 24:
        return False
    for c in f:
        if c not in NAME_OK:
            return False
    return True


def country_ok(f):
    if len(f) != 2:
        return False
    return 65 <= f[0] <= 90 and 65 <= f[1] <= 90


def number(f, lo, hi):
    if not f:
        return None
    v = 0
    for c in f:
        if c < 48 or c > 57:
            return None
        v = v * 10 + (c - 48)
    if v < lo or v > hi:
        return None
    return v


def zero_report():
    sys.stdout.buffer.write(b'users 0 orders 0 bad 0 unmatched 0\ntotal 0\n')


def main():
    data = sys.stdin.buffer.read()
    if not data:
        zero_report()
        return 0
    lines = data.split(b'\n')
    if lines[-1] == b'':
        lines.pop()
    ui = None
    for i, line in enumerate(lines):
        if line == b'#users':
            ui = i
            break
    if ui is None:
        zero_report()
        return 0
    oi = None
    for i in range(ui + 1, len(lines)):
        if lines[i] == b'#orders':
            oi = i
            break
    if oi is None:
        zero_report()
        return 0
    users = {}
    good_users = 0
    bad = 0
    for line in lines[ui + 1:oi]:
        f = line.split(b'\t')
        if len(f) != 3:
            bad += 1
            continue
        uid = number(f[0], 1, 2000000000)
        if uid is None or not name_ok(f[1]) or not country_ok(f[2]) or uid in users:
            bad += 1
            continue
        users[uid] = (f[1], f[2])
        good_users += 1
    uamt = {}
    unum = {}
    camt = {}
    cnum = {}
    good_orders = 0
    unmatched = 0
    for line in lines[oi + 1:]:
        f = line.split(b'\t')
        if len(f) != 3:
            bad += 1
            continue
        oid = number(f[0], 1, 2000000000)
        uid = number(f[1], 1, 2000000000)
        amt = number(f[2], 0, 100000000)
        if oid is None or uid is None or amt is None:
            bad += 1
            continue
        good_orders += 1
        u = users.get(uid)
        if u is None:
            unmatched += 1
            continue
        uamt[uid] = uamt.get(uid, 0) + amt
        unum[uid] = unum.get(uid, 0) + 1
        cc = u[1]
        camt[cc] = camt.get(cc, 0) + amt
        cnum[cc] = cnum.get(cc, 0) + 1
    out = ['users %d orders %d bad %d unmatched %d' % (good_users, good_orders, bad, unmatched)]
    for cc in sorted(camt, key=lambda c: (-camt[c], c)):
        out.append('country %s orders %d amount %d' % (cc.decode(), cnum[cc], camt[cc]))
    order = sorted(uamt, key=lambda u: (-uamt[u], u))
    for uid in order[:10]:
        out.append('user %d %s %d' % (uid, users[uid][0].decode(), uamt[uid]))
    out.append('total %d' % sum(uamt.values()))
    sys.stdout.buffer.write(('\n'.join(out) + '\n').encode())
    return 0


if __name__ == '__main__':
    sys.exit(main())
