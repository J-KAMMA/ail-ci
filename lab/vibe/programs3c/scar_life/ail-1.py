import sys

CODE = {'0': 0, '1': 1, '2': 2, '3': 3, '4': 4, '5': 5, '6': 6, '7': 7, '8': 8, '9': 9,
        'A': 10, 'B': 11, 'C': 12}
DIG = "0123456789"


def bad():
    sys.exit(1)


def parse_codes(s):
    vals = []
    prev = -1
    for ch in s:
        if ch not in CODE:
            return None
        v = CODE[ch]
        if v <= prev:
            return None
        vals.append(v)
        prev = v
    return vals


def main():
    if len(sys.argv) != 3:
        bad()

    rule = sys.argv[1]
    if len(rule) < 1 or rule[0] != 'B':
        bad()
    idx = rule.find('/')
    if idx < 0:
        bad()
    rest = rule[idx + 1:]
    if len(rest) < 1 or rest[0] != 'S':
        bad()
    bl = parse_codes(rule[1:idx])
    sl = parse_codes(rest[1:])
    if bl is None or sl is None:
        bad()

    gs = sys.argv[2]
    if len(gs) == 0:
        bad()
    for ch in gs:
        if ch not in DIG:
            bad()
    G = int(gs)
    if G > 100000:
        bad()

    data = sys.stdin.buffer.read().decode('latin-1')
    if data.endswith('\n'):
        body = data[:-1]
    else:
        body = data
    lines = body.split('\n')

    parts = lines[0].split(' ')
    if len(parts) != 2:
        bad()
    for t in parts:
        if len(t) == 0:
            bad()
        for ch in t:
            if ch not in DIG:
                bad()
        if len(t) > 1 and t[0] == '0':
            bad()
    W = int(parts[0])
    H = int(parts[1])
    if W < 1 or W > 4096 or H < 1 or H > 4096:
        bad()
    if len(lines) != H + 1:
        bad()
    rows = lines[1:]
    for row in rows:
        if len(row) != W:
            bad()
        for ch in row:
            if ch != '.' and ch != 'o':
                bad()

    N = W * H
    st = []
    for row in rows:
        for ch in row:
            st.append(1 if ch == 'o' else 0)

    born = [0] * 13
    surv = [0] * 13
    for v in bl:
        born[v] = 1
    for v in sl:
        surv[v] = 1

    rowm = [(r - 1) % H for r in range(H)]
    rowp = [(r + 1) % H for r in range(H)]
    colm = [(c - 1) % W for c in range(W)]
    colp = [(c + 1) % W for c in range(W)]

    out = []
    for g in range(1, G + 1):
        A = [1 if x == 1 else 0 for x in st]
        new = [0] * N
        na = 0
        ns = 0
        for r in range(H):
            up = rowm[r] * W
            dn = rowp[r] * W
            base = r * W
            for c in range(W):
                l = colm[c]
                rt = colp[c]
                w = 2 * (A[up + c] + A[dn + c] + A[base + l] + A[base + rt]) \
                    + A[up + l] + A[up + rt] + A[dn + l] + A[dn + rt]
                s = st[base + c]
                if s == 1:
                    if surv[w]:
                        new[base + c] = 1
                        na += 1
                    else:
                        new[base + c] = 2
                        ns += 1
                elif s == 0:
                    if born[w]:
                        new[base + c] = 1
                        na += 1
        st = new
        out.append(str(g) + " " + str(na) + " " + str(ns) + "\n")

    M = ['.', 'o', 'x']
    for r in range(H):
        base = r * W
        out.append("".join(M[st[base + c]] for c in range(W)) + "\n")

    sys.stdout.write("".join(out))
    sys.exit(0)


main()
