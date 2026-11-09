import re
import sys


def fail():
    sys.stderr.write("error\n")
    sys.exit(1)


def parse_codes(s):
    vals = [int(ch, 16) for ch in s]
    for i in range(1, len(vals)):
        if vals[i] <= vals[i - 1]:
            fail()
    return set(vals)


def main():
    args = sys.argv[1:]
    if len(args) != 2:
        fail()
    rule, gens_s = args

    m = re.fullmatch(r'B([0-9A-C]*)/S([0-9A-C]*)', rule)
    if not m:
        fail()
    Bset = parse_codes(m.group(1))
    Sset = parse_codes(m.group(2))

    if not re.fullmatch(r'[0-9]+', gens_s):
        fail()
    gens = int(gens_s)
    if gens > 100000:
        fail()

    data = sys.stdin.buffer.read()
    if not data:
        fail()
    if data.endswith(b'\n'):
        data = data[:-1]
    lines = data.split(b'\n')

    hm = re.fullmatch(rb'([1-9][0-9]*) ([1-9][0-9]*)', lines[0])
    if not hm:
        fail()
    W = int(hm.group(1))
    H = int(hm.group(2))
    if not (1 <= W <= 4096 and 1 <= H <= 4096):
        fail()
    if len(lines) != H + 1:
        fail()
    for line in lines[1:]:
        if len(line) != W or not re.fullmatch(rb'[.o]*', line):
            fail()

    # state: 0 dead, 1 alive, 2 scar
    state = [[1 if c == ord('o') else 0 for c in line] for line in lines[1:]]

    lx = [(x - 1) % W for x in range(W)]
    rx = [(x + 1) % W for x in range(W)]
    ym = [(y - 1) % H for y in range(H)]
    yp = [(y + 1) % H for y in range(H)]

    out = []
    for g in range(1, gens + 1):
        A = [[1 if v == 1 else 0 for v in row] for row in state]
        new = [[0] * W for _ in range(H)]
        for y in range(H):
            up = A[ym[y]]
            dn = A[yp[y]]
            cur = A[y]
            srow = state[y]
            nrow = new[y]
            for x in range(W):
                l = lx[x]
                r = rx[x]
                w = 2 * (up[x] + dn[x] + cur[l] + cur[r]) + up[l] + up[r] + dn[l] + dn[r]
                s = srow[x]
                if s == 1:
                    nrow[x] = 1 if w in Sset else 2
                elif s == 0:
                    nrow[x] = 1 if w in Bset else 0
                else:
                    nrow[x] = 0
        state = new
        alive = sum(row.count(1) for row in state)
        scars = sum(row.count(2) for row in state)
        out.append(f"{g} {alive} {scars}\n")

    for row in state:
        out.append("".join(".ox"[v] for v in row) + "\n")

    sys.stdout.write("".join(out))
    sys.exit(0)


if __name__ == "__main__":
    main()
