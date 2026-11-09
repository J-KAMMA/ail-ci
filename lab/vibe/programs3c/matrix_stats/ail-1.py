import sys

LO = -9223372036854775807 - 1
POS_LIM = "9223372036854775807"
NEG_LIM = "9223372036854775808"


def fail():
    sys.stdout.write("error\n")
    sys.exit(2)


def is_digits(s):
    if len(s) == 0:
        return False
    for ch in s:
        if ch < "0" or ch > "9":
            return False
    return True


def parse_dim(t):
    if not is_digits(t):
        return -1
    s = t.lstrip("0")
    if s == "":
        return 0
    if len(s) > 6:
        return -1
    return int(s)


def parse_int(t):
    neg = False
    s = t
    if len(s) > 0 and (s[0] == "+" or s[0] == "-"):
        neg = s[0] == "-"
        s = s[1:]
    if not is_digits(s):
        return None
    s = s.lstrip("0")
    if s == "":
        return 0
    if neg:
        if len(s) > 19 or (len(s) == 19 and s > NEG_LIM):
            return None
        if s == NEG_LIM:
            return LO
    else:
        if len(s) > 19 or (len(s) == 19 and s > POS_LIM):
            return None
    v = int(s)
    if neg:
        v = -v
    return v


def main():
    data = sys.stdin.read()
    if data.endswith("\n"):
        data = data[:-1]
    lines = data.split("\n")

    hdr = lines[0].split()
    if len(hdr) != 2:
        fail()
    R = parse_dim(hdr[0])
    C = parse_dim(hdr[1])
    if R < 0 or C < 0:
        fail()
    if R > 10000 or C > 10000 or R * C > 1000000:
        fail()
    if len(lines) != R + 1:
        fail()

    grid = []
    for i in range(R):
        toks = lines[i + 1].split()
        if len(toks) != C:
            fail()
        row = []
        for t in toks:
            v = parse_int(t)
            if v is None:
                fail()
            row.append(v)
        grid.append(row)

    out = []
    col = [0] * C
    best = LO
    has = False
    br = -1
    bc = -1
    for i in range(R):
        row = grid[i]
        s = 0
        for j in range(C):
            v = row[j]
            s += v
            col[j] += v
            if (not has) or v > best:
                has = True
                best = v
                br = i
                bc = j
        out.append("row " + str(i) + " " + str(s) + "\n")

    for j in range(C):
        out.append("col " + str(j) + " " + str(col[j]) + "\n")

    if has:
        out.append("max " + str(best) + " at " + str(br) + " " + str(bc) + "\n")
    else:
        out.append("max none\n")

    sys.stdout.write("".join(out))


main()
