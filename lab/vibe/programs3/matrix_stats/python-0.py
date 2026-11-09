import re
import sys

_INT_RE = re.compile(rb'[+-]?[0-9]+')
_UINT_RE = re.compile(rb'[0-9]+')
_MIN_I64 = -(1 << 63)
_MAX_I64 = (1 << 63) - 1


def _error():
    sys.stdout.write("error\n")
    raise SystemExit(2)


def _parse_int(token):
    if _INT_RE.fullmatch(token) is None:
        return None

    if token[0] == 43 or token[0] == 45:
        negative = token[0] == 45
        digits = token[1:]
    else:
        negative = False
        digits = token

    digits = digits.lstrip(b"0")
    if not digits:
        return 0
    if len(digits) > 19:
        return None

    value = int(digits)
    if negative:
        value = -value
    if value < _MIN_I64 or value > _MAX_I64:
        return None
    return value


def _parse_dimension(token):
    if _UINT_RE.fullmatch(token) is None:
        return None

    digits = token.lstrip(b"0")
    if not digits:
        return 0
    if len(digits) > 5:
        return None
    return int(digits)


def main():
    data = sys.stdin.buffer.read()
    parts = data.split(b"\n")

    header = parts[0].split()
    if len(header) != 2:
        _error()

    rows = _parse_dimension(header[0])
    cols = _parse_dimension(header[1])
    if rows is None or cols is None:
        _error()
    if rows > 10000 or cols > 10000 or rows * cols > 1000000:
        _error()

    row_fields = parts[1:]
    row_sums = []
    col_sums = [0] * cols
    max_value = None
    max_row = 0
    max_col = 0

    for i in range(rows):
        if i >= len(row_fields):
            _error()

        tokens = row_fields[i].split()
        if len(tokens) != cols:
            _error()

        row_total = 0
        for j, token in enumerate(tokens):
            value = _parse_int(token)
            if value is None:
                _error()

            row_total += value
            col_sums[j] += value

            if max_value is None or value > max_value:
                max_value = value
                max_row = i
                max_col = j

        row_sums.append(row_total)

    leftover = row_fields[rows:]
    if leftover:
        if not (
            len(leftover) == 1
            and leftover[0] == b""
            and data.endswith(b"\n")
        ):
            _error()

    output = []
    for i, value in enumerate(row_sums):
        output.append(f"row {i} {value}")
    for j, value in enumerate(col_sums):
        output.append(f"col {j} {value}")

    if max_value is None:
        output.append("max none")
    else:
        output.append(f"max {max_value} at {max_row} {max_col}")

    sys.stdout.write("\n".join(output) + "\n")


if __name__ == "__main__":
    main()
