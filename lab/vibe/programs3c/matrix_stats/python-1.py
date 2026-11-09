import re
import sys

DIG = re.compile(r"[0-9]+")
INT = re.compile(r"[+-]?[0-9]+")
LO = -(2 ** 63)
HI = 2 ** 63 - 1


def fail():
    sys.stdout.write("error\n")
    sys.exit(2)


def main():
    raw = sys.stdin.buffer.read()
    try:
        text = raw.decode("ascii")
    except UnicodeDecodeError:
        fail()

    lines = text.split("\n")
    if lines and lines[-1] == "":
        lines.pop()
    if not lines:
        fail()

    header = lines[0].split()
    if len(header) != 2 or not all(DIG.fullmatch(t) for t in header):
        fail()
    R = int(header[0])
    C = int(header[1])
    if R > 10000 or C > 10000 or R * C > 1000000:
        fail()

    rest = lines[1:]
    if len(rest) < R:
        fail()
    for extra in rest[R:]:
        if extra.strip():
            fail()

    matrix = []
    for i in range(R):
        toks = rest[i].split()
        if len(toks) != C:
            fail()
        row = []
        for t in toks:
            if not INT.fullmatch(t):
                fail()
            v = int(t)
            if v < LO or v > HI:
                fail()
            row.append(v)
        matrix.append(row)

    out = []
    row_sums = []
    col_sums = [0] * C
    best = None
    best_r = best_c = 0
    for i, row in enumerate(matrix):
        s = 0
        for j, v in enumerate(row):
            s += v
            col_sums[j] += v
            if best is None or v > best:
                best = v
                best_r = i
                best_c = j
        row_sums.append(s)

    for i, s in enumerate(row_sums):
        out.append(f"row {i} {s}\n")
    for j, s in enumerate(col_sums):
        out.append(f"col {j} {s}\n")
    if best is None:
        out.append("max none\n")
    else:
        out.append(f"max {best} at {best_r} {best_c}\n")

    sys.stdout.write("".join(out))
    sys.exit(0)


if __name__ == "__main__":
    main()
