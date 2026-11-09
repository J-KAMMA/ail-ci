import sys

MAXV = 9223372036854775807
MINV = -9223372036854775807 - 1


def fail():
    print("error")
    sys.exit(2)


def parse_nonneg(tok):
    if tok == "":
        return None
    for ch in tok:
        if ch < "0" or ch > "9":
            return None
    s = tok.lstrip("0")
    if s == "":
        return 0
    if len(s) > 5:
        return None
    return int(s)


def parse_int(tok):
    s = tok
    neg = False
    if s[:1] == "-" or s[:1] == "+":
        neg = s[0] == "-"
        s = s[1:]
    if s == "":
        return None
    for ch in s:
        if ch < "0" or ch > "9":
            return None
    s = s.lstrip("0")
    if s == "":
        return 0
    if len(s) > 19:
        return None
    if len(s) == 19:
        lim = "9223372036854775808" if neg else "9223372036854775807"
        if s > lim:
            return None
    if neg and s == "9223372036854775808":
        return MINV
    v = int(s)
    if neg:
        return -v
    return v


def main():
    data = sys.stdin.buffer.read().decode("latin-1")
    if data == "":
        fail()
    lines = data.split("\n")
    if data.endswith("\n"):
        lines.pop()
    if len(lines) == 0:
        fail()

    hdr = lines[0].split()
    if len(hdr) != 2:
        fail()
    R = parse_nonneg(hdr[0])
    C = parse_nonneg(hdr[1])
    if R is None or C is None:
        fail()
    if R > 10000 or C > 10000:
        fail()
    if R * C > 1000000:
        fail()

    if len(lines) - 1 < R:
        fail()

    rows = []
    for i in range(R):
        toks = lines[1 + i].split()
        if len(toks) != C:
            fail()
        row = []
        for t in toks:
            v = parse_int(t)
            if v is None:
                fail()
            row.append(v)
        rows.append(row)

    out = []

    for i in range(R):
        total = 0
        r = rows[i]
        for j in range(C):
            total += r[j]
        out.append("row " + str(i) + " " + str(total) + "\n")

    colsums = [0] * C
    for i in range(R):
        r = rows[i]
        for j in range(C):
            colsums[j] += r[j]

    for j in range(C):
        out.append("col " + str(j) + " " + str(colsums[j]) + "\n")

    if R * C == 0:
        out.append("max none\n")
    else:
        have = False
        best = 0
        br = 0
        bc = 0
        for i in range(R):
            r = rows[i]
            for j in range(C):
                v = r[j]
                if not have or v > best:
                    have = True
                    best = v
                    br = i
                    bc = j
        out.append("max " + str(best) + " at " + str(br) + " " + str(bc) + "\n")

    sys.stdout.write("".join(out))
    sys.exit(0)


main()
