import sys
import re

CODES = "0123456789ABC"


def parse_rule(s):
    m = re.fullmatch(r"B([0-9A-C]*)/S([0-9A-C]*)", s, re.ASCII)
    if not m:
        return None
    out = []
    for part in m.groups():
        idx = [CODES.index(c) for c in part]
        if any(idx[i] >= idx[i + 1] for i in range(len(idx) - 1)):
            return None
        out.append(idx)
    return out


def fail():
    sys.exit(1)


def main():
    if len(sys.argv) != 3:
        fail()
    rule = parse_rule(sys.argv[1])
    if rule is None:
        fail()
    g = sys.argv[2]
    if not re.fullmatch(r"[0-9]+", g, re.ASCII):
        fail()
    gens = int(g)
    if gens > 100000:
        fail()
    data = sys.stdin.buffer.read()
    if data.endswith(b"\n"):
        data = data[:-1]
    lines = data.split(b"\n")
    m = re.fullmatch(rb"([1-9][0-9]*) ([1-9][0-9]*)", lines[0])
    if not m:
        fail()
    W = int(m.group(1))
    H = int(m.group(2))
    if W > 4096 or H > 4096:
        fail()
    rows = lines[1:]
    if len(rows) != H:
        fail()
    for r in rows:
        if len(r) != W or r.strip(b".o"):
            fail()
    N = W * H
    # bit index i = y*W + x
    flat = b"".join(rows)
    A = int(flat.translate(bytes.maketrans(b".o", b"01"))[::-1], 2) if N else 0
    full = (1 << N) - 1
    col0 = 0
    for y in range(H):
        col0 |= 1 << (y * W)
    colL = col0 << (W - 1)
    ncol0 = full ^ col0
    ncolL = full ^ colL
    Bset = set(rule[0])
    Sset = set(rule[1])

    def eqmask(w, b0, b1, b2, b3):
        r = b0 if w & 1 else full ^ b0
        r &= b1 if w & 2 else full ^ b1
        r &= b2 if w & 4 else full ^ b2
        r &= b3 if w & 8 else full ^ b3
        return r

    def rowl(v):  # value from x-1
        return ((v << 1) & ncol0) | ((v >> (W - 1)) & col0)

    def rowr(v):  # value from x+1
        return ((v >> 1) & ncolL) | ((v << (W - 1)) & colL)

    def up(v):  # value from y-1
        return ((v << W) & full) | (v >> (N - W))

    def down(v):  # value from y+1
        return (v >> W) | ((v << (N - W)) & full)

    X = 0
    out = []
    for gi in range(1, gens + 1):
        L = rowl(A)
        R = rowr(A)
        U = up(A)
        D = down(A)
        UL = rowl(U)
        UR = rowr(U)
        DL = rowl(D)
        DR = rowr(D)

        def count4(a, b, c, d):
            s1 = a ^ b
            c1 = a & b
            s2 = c ^ d
            c2 = c & d
            k = s1 & s2
            return s1 ^ s2, c1 ^ c2 ^ k, c1 & c2

        o0, o1, o2 = count4(L, R, U, D)
        d0, d1, d2 = count4(UL, UR, DL, DR)
        w0 = d0
        w1 = d1 ^ o0
        cc = d1 & o0
        w2 = d2 ^ o1 ^ cc
        c2 = (d2 & o1) | (d2 & cc) | (o1 & cc)
        w3 = o2 ^ c2
        bm = 0
        for w in Bset:
            bm |= eqmask(w, w0, w1, w2, w3)
        sm = 0
        for w in Sset:
            sm |= eqmask(w, w0, w1, w2, w3)
        dead = full ^ (A | X)
        newA = (A & sm) | (dead & bm)
        X = A & (full ^ sm)
        A = newA
        out.append("%d %d %d\n" % (gi, A.bit_count(), X.bit_count()))
    sa = format(A, "0%db" % N)[::-1]
    sx = format(X, "0%db" % N)[::-1]
    if X:
        cells = [("o" if a == "1" else ("x" if x == "1" else ".")) for a, x in zip(sa, sx)]
        s = "".join(cells)
    else:
        s = sa.replace("1", "o").replace("0", ".")
    for y in range(H):
        out.append(s[y * W:(y + 1) * W] + "\n")
    sys.stdout.write("".join(out))


main()
