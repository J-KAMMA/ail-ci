import sys


def die():
    sys.stdout.write("error\n")
    sys.exit(2)


def parse_header_num(tok):
    if len(tok) == 0:
        return -1
    for ch in tok:
        if ch < 48 or ch > 57:
            return -1
    digits = tok.lstrip(b"0")
    if len(digits) == 0:
        return 0
    if len(digits) > 5:
        return -1
    if len(digits) == 5 and digits > b"10000":
        return -1
    val = 0
    for ch in digits:
        val = val * 10 + (ch - 48)
    return val


def parse_int_token(tok):
    if len(tok) == 0:
        return None

    sign = 1
    body = tok
    first = tok[0]

    if first == 43:
        body = tok[1:]
    elif first == 45:
        sign = -1
        body = tok[1:]

    if len(body) == 0:
        return None

    for ch in body:
        if ch < 48 or ch > 57:
            return None

    digits = body.lstrip(b"0")
    if len(digits) == 0:
        return 0

    if sign > 0:
        limit = b"9223372036854775807"
    else:
        limit = b"9223372036854775808"

    if len(digits) > len(limit):
        return None
    if len(digits) == len(limit) and digits > limit:
        return None

    val = 0
    if sign > 0:
        for ch in digits:
            val = val * 10 + (ch - 48)
    else:
        for ch in digits:
            val = val * 10 - (ch - 48)
    return val


def main():
    data = sys.stdin.buffer.read()
    if len(data) == 0:
        die()

    pos = data.find(b"\n")
    if pos < 0:
        header = data
        rest = b""
        has_nl = False
    else:
        header = data[:pos]
        rest = data[pos + 1:]
        has_nl = True

    if header.endswith(b"\r"):
        header = header[:-1]

    header_tokens = header.split()
    if len(header_tokens) != 2:
        die()

    R = parse_header_num(header_tokens[0])
    C = parse_header_num(header_tokens[1])

    if R < 0 or C < 0:
        die()
    if R > 10000 or C > 10000:
        die()
    if R * C > 1000000:
        die()

    rows = []

    if R == 0:
        if len(rest) != 0:
            die()
    else:
        if not has_nl:
            die()

        parts = rest.split(b"\n")

        if rest.endswith(b"\n"):
            if len(parts) - 1 == R:
                rows = parts[:-1]
            elif len(parts) == R:
                rows = parts
            else:
                die()
        else:
            if len(parts) == R:
                rows = parts
            else:
                die()

    col_sums = [0] * C
    row_sums = []

    max_val = 0
    max_r = 0
    max_c = 0
    max_seen = False

    for i in range(R):
        line = rows[i]

        if line.endswith(b"\r"):
            line = line[:-1]
        line = line.rstrip(b" ")

        row_sum = 0

        if C == 0:
            if len(line) != 0:
                die()
        else:
            if line.startswith(b" "):
                die()
            if len(line) == 0:
                die()

            raw_tokens = line.split(b" ")
            tokens = [t for t in raw_tokens if len(t) != 0]

            if len(tokens) != C:
                die()

            for j in range(C):
                val = parse_int_token(tokens[j])
                if val is None:
                    die()

                row_sum += val
                col_sums[j] += val

                if not max_seen or val > max_val:
                    max_val = val
                    max_r = i
                    max_c = j
                    max_seen = True

        row_sums.append(row_sum)

    out = []

    for i in range(R):
        out.append("row " + str(i) + " " + str(row_sums[i]) + "\n")

    for j in range(C):
        out.append("col " + str(j) + " " + str(col_sums[j]) + "\n")

    if R * C == 0:
        out.append("max none\n")
    else:
        out.append("max " + str(max_val) + " at " + str(max_r) + " " + str(max_c) + "\n")

    sys.stdout.write("".join(out))


main()
