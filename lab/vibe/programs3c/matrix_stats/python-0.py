import re
import sys

INT_RE = re.compile(r'[+-]?[0-9]+')
HEADER_RE = re.compile(r'[0-9]+')
LO = -(1 << 63)
HI = (1 << 63) - 1


def fail():
    sys.stdout.write("error\n")
    sys.exit(2)


def parse_int(tok):
    if not INT_RE.fullmatch(tok):
        fail()
    sign = 1
    digits = tok
    if digits[0] in '+-':
        if digits[0] == '-':
            sign = -1
        digits = digits[1:]
    digits = digits.lstrip('0') or '0'
    if len(digits) > 19:
        fail()
    v = sign * int(digits)
    if v < LO or v > HI:
        fail()
    return v


def main():
    data = sys.stdin.buffer.read()
    try:
        text = data.decode('ascii')
    except UnicodeDecodeError:
        fail()

    if text == '':
        fail()

    lines = text.split('\n')
    if lines and lines[-1] == '':
        lines.pop()
    if not lines:
        fail()

    header = lines[0].split()
    if len(header) != 2 or not all(HEADER_RE.fullmatch(t) for t in header):
        fail()
    R = int(header[0])
    C = int(header[1])
    if R > 10000 or C > 10000 or R * C > 1000000:
        fail()

    body = lines[1:]
    if len(body) != R:
        fail()

    matrix = []
    for line in body:
        toks = line.split()
        if len(toks) != C:
            fail()
        matrix.append([parse_int(t) for t in toks])

    row_sums = [sum(r) for r in matrix]

    if R == 0:
        col_sums = [0] * C
    else:
        col_sums = [sum(col) for col in zip(*matrix)]

    best = None
    bi = bj = 0
    for i, row in enumerate(matrix):
        for j, v in enumerate(row):
            if best is None or v > best:
                best = v
                bi = i
                bj = j

    out = []
    for i, s in enumerate(row_sums):
        out.append(f"row {i} {s}\n")
    for j, s in enumerate(col_sums):
        out.append(f"col {j} {s}\n")
    if best is None:
        out.append("max none\n")
    else:
        out.append(f"max {best} at {bi} {bj}\n")

    sys.stdout.write("".join(out))
    sys.exit(0)


if __name__ == "__main__":
    main()
