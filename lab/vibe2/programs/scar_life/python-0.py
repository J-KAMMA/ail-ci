import sys


def parse_rule(rule):
    if len(rule) < 3 or rule[0] != 'B':
        return None

    slash = rule.find('/')
    if slash < 0:
        return None
    if slash + 1 >= len(rule) or rule[slash + 1] != 'S':
        return None

    birth_part = rule[1:slash]
    survive_part = rule[slash + 2:]

    birth = [False] * 13
    previous = -1
    for ch in birth_part:
        if '0' <= ch <= '9':
            value = ord(ch) - 48
        elif ch == 'A':
            value = 10
        elif ch == 'B':
            value = 11
        elif ch == 'C':
            value = 12
        else:
            return None
        if value <= previous:
            return None
        previous = value
        birth[value] = True

    survive = [False] * 13
    previous = -1
    for ch in survive_part:
        if '0' <= ch <= '9':
            value = ord(ch) - 48
        elif ch == 'A':
            value = 10
        elif ch == 'B':
            value = 11
        elif ch == 'C':
            value = 12
        else:
            return None
        if value <= previous:
            return None
        previous = value
        survive[value] = True

    return birth, survive


def parse_gens(text):
    if not text:
        return None

    for ch in text:
        if ch < '0' or ch > '9':
            return None

    trimmed = text.lstrip('0')
    if trimmed == '':
        return 0
    if len(trimmed) > 6:
        return None

    value = int(trimmed)
    if value > 100000:
        return None
    return value


def parse_grid(data):
    newline = data.find(b'\n')
    if newline < 0:
        return None

    header = data[:newline]
    parts = header.split(b' ')
    if len(parts) != 2:
        return None

    numbers = []
    for part in parts:
        if not part or len(part) > 4:
            return None
        if part[0] < 49 or part[0] > 57:
            return None
        for ch in part[1:]:
            if ch < 48 or ch > 57:
                return None
        numbers.append(int(part))

    width, height = numbers
    if not (1 <= width <= 4096 and 1 <= height <= 4096):
        return None

    body = data[newline + 1:]
    if body.endswith(b'\n'):
        body = body[:-1]

    rows = body.split(b'\n')
    if len(rows) != height:
        return None

    grid = bytearray()
    table = bytes(1 if i == 111 else 0 for i in range(256))

    for row in rows:
        if len(row) != width:
            return None
        if row.translate(None, b'.o'):
            return None
        grid.extend(row.translate(table))

    return width, height, grid


def evolve(width, height, grid, generations, birth, survive):
    size = width * height

    previous_row = [(r - 1) % height for r in range(height)]
    next_row = [(r + 1) % height for r in range(height)]
    previous_col = [(c - 1) % width for c in range(width)]
    next_col = [(c + 1) % width for c in range(width)]

    transition = bytearray(3 * 13)
    for weight in range(13):
        transition[weight] = 1 if birth[weight] else 0
        transition[13 + weight] = 1 if survive[weight] else 2
        transition[26 + weight] = 0

    out = sys.stdout.buffer
    lines = []

    for generation in range(1, generations + 1):
        weights = bytearray(size)

        for r in range(height):
            row_start = r * width
            up_start = previous_row[r] * width
            down_start = next_row[r] * width

            for c in range(width):
                if grid[row_start + c] == 1:
                    left = previous_col[c]
                    right = next_col[c]

                    weights[up_start + c] += 2
                    weights[down_start + c] += 2
                    weights[row_start + left] += 2
                    weights[row_start + right] += 2

                    weights[up_start + left] += 1
                    weights[up_start + right] += 1
                    weights[down_start + left] += 1
                    weights[down_start + right] += 1

        for i in range(size):
            grid[i] = transition[grid[i] * 13 + weights[i]]

        alive = grid.count(b'\x01')
        scars = grid.count(b'\x02')
        lines.append(f"{generation} {alive} {scars}\n")

    if lines:
        out.write("".join(lines).encode("ascii"))

    output_table = bytes.maketrans(b'\x00\x01\x02', b'.ox')
    for r in range(height):
        start = r * width
        out.write(bytes(grid[start:start + width]).translate(output_table))
        out.write(b'\n')


def main():
    args = sys.argv[1:]
    if len(args) != 2:
        return 1

    parsed_rule = parse_rule(args[0])
    if parsed_rule is None:
        return 1

    generations = parse_gens(args[1])
    if generations is None:
        return 1

    data = sys.stdin.buffer.read()
    parsed_grid = parse_grid(data)
    if parsed_grid is None:
        return 1

    width, height, grid = parsed_grid
    del data

    birth, survive = parsed_rule
    evolve(width, height, grid, generations, birth, survive)
    return 0


if __name__ == "__main__":
    sys.exit(main())
