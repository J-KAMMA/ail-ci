import re
import sys


def fail():
    sys.stderr.write("error\n")
    sys.exit(1)


CODE = {str(i): i for i in range(10)}
CODE.update({"A": 10, "B": 11, "C": 12})


def parse_codes(s):
    table = [False] * 13
    prev = -1
    for ch in s:
        v = CODE[ch]
        if v <= prev:
            return None
        prev = v
        table[v] = True
    return table


def step(g, W, H, Bset, Sset):
    a = [[1 if s == 1 else 0 for s in row] for row in g]
    ng = []
    for y in range(H):
        up = a[(y - 1) % H]
        dn = a[(y + 1) % H]
        cur = a[y]
        srow = g[y]
        vs = [up[x] + dn[x] for x in range(W)]
        nrow = [0] * W
        for x in range(W):
            xl = x - 1 if x > 0 else W - 1
            xr = x + 1 if x < W - 1 else 0
            w = 2 * vs[x] + 2 * (cur[xl] + cur[xr]) + vs[xl] + vs[xr]
            s = srow[x]
            if s == 1:
                nrow[x] = 1 if Sset[w] else 2
            elif s == 0:
                nrow[x] = 1 if Bset[w] else 0
            else:
                nrow[x] = 0
        ng.append(nrow)
    return ng


def main():
    args = sys.argv[1:]
    if len(args) != 2:
        fail()
    rule, gens_s = args

    m = re.fullmatch(r"B([0-9A-C]*)/S([0-9A-C]*)", rule)
    if not m:
        fail()
    Bset = parse_codes(m.group(1))
    Sset = parse_codes(m.group(2))
    if Bset is None or Sset is None:
        fail()

    if not re.fullmatch(r"[0-9]+", gens_s):
        fail()
    GENS = int(gens_s)
    if GENS > 100000:
        fail()

    data = sys.stdin.buffer.read()
    if data.endswith(b"\n"):
        body = data[:-1]
    else:
        body = data
    lines = body.split(b"\n")

    hm = re.fullmatch(rb"([1-9][0-9]*) ([1-9][0-9]*)", lines[0])
    if not hm:
        fail()
    W = int(hm.group(1))
    H = int(hm.group(2))
    if W < 1 or W > 4096 or H < 1 or H > 4096:
        fail()
    if len(lines) != H + 1:
        fail()

    grid_lines = lines[1:]
    for line in grid_lines:
        if len(line) != W or not re.fullmatch(rb"[.o]*", line):
            fail()

    g = [[1 if c == 111 else 0 for c in line] for line in grid_lines]

    out = []
    for gen in range(1, GENS + 1):
        g = step(g, W, H, Bset, Sset)
        alive = sum(row.count(1) for row in g)
        scars = sum(row.count(2) for row in g)
        out.append(f"{gen} {alive} {scars}\n")

    chars = {0: ".", 1: "o", 2: "x"}
    for row in g:
        out.append("".join(chars[s] for s in row) + "\n")

    sys.stdout.write("".join(out))
    sys.stdout.flush()
    sys.exit(0)


if __name__ == "__main__":
    main()
