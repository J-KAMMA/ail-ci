import re
import sys

RULE_RE = re.compile(r"B([0-9ABC]*)/S([0-9ABC]*)")
TRANS_IN = bytes.maketrans(b".o", b"\x00\x01")
TRANS_OUT = bytes.maketrans(b"\x00\x01\x02", b".ox")


def fail():
    raise SystemExit(1)


def parse_dim(token):
    if not token or len(token) > 4 or token[0] == 48:
        fail()
    for b in token:
        if b < 48 or b > 57:
            fail()
    value = int(token)
    if value < 1 or value > 4096:
        fail()
    return value


def parse_rule(rule):
    match = RULE_RE.fullmatch(rule)
    if match is None:
        fail()
    birth = [False] * 13
    survive = [False] * 13
    for part, table in ((match.group(1), birth), (match.group(2), survive)):
        previous = -1
        for ch in part:
            if ch == "A":
                value = 10
            elif ch == "B":
                value = 11
            elif ch == "C":
                value = 12
            else:
                value = ord(ch) - 48
            if value <= previous:
                fail()
            previous = value
            table[value] = True
    return birth, survive


def parse_gens(text):
    if not text:
        fail()
    for ch in text:
        if ch < "0" or ch > "9":
            fail()
    trimmed = text.lstrip("0")
    if not trimmed:
        return 0
    if len(trimmed) > 6:
        fail()
    if len(trimmed) == 6 and trimmed > "100000":
        fail()
    return int(trimmed)


def read_grid():
    data = sys.stdin.buffer.read()
    newline = data.find(b"\n")
    if newline < 0:
        fail()

    header = data[:newline]
    parts = header.split(b" ")
    if len(parts) != 2:
        fail()

    width = parse_dim(parts[0])
    height = parse_dim(parts[1])

    rest = data[newline + 1:]
    cell_count = width * height
    minimum = cell_count + height - 1
    if len(rest) != minimum and len(rest) != minimum + 1:
        fail()

    old = bytearray(cell_count)
    position = 0

    for y in range(height):
        chunk = rest[position:position + width]
        if len(chunk) != width:
            fail()
        if chunk.translate(None, b".o"):
            fail()

        base = y * width
        old[base:base + width] = chunk.translate(TRANS_IN)
        position += width

        if y != height - 1:
            if position >= len(rest) or rest[position] != 10:
                fail()
            position += 1
        else:
            if position == len(rest):
                pass
            elif position + 1 == len(rest) and rest[position] == 10:
                position += 1
            else:
                fail()

    return width, height, old


def simulate(width, height, old, gens, birth, survive):
    cell_count = width * height
    counts = []

    if gens == 0:
        return old, counts

    left = [(x - 1) % width for x in range(width)]
    right = [(x + 1) % width for x in range(width)]
    up = [(y - 1) % height for y in range(height)]
    down = [(y + 1) % height for y in range(height)]

    use_cycle = gens > 1000 and cell_count <= 4096
    seen = {bytes(old): 0} if use_cycle else None
    max_seen = max(500, min(20000, 20_000_000 // cell_count))

    step = 0

    while step < gens:
        new = bytearray(cell_count)
        alive_count = 0
        scar_count = 0
        current = old

        for y in range(height):
            base = y * width
            upper_base = up[y] * width
            lower_base = down[y] * width

            for x in range(width):
                xl = left[x]
                xr = right[x]

                weight = (
                    2 * (
                        (current[upper_base + x] & 1)
                        + (current[lower_base + x] & 1)
                        + (current[base + xl] & 1)
                        + (current[base + xr] & 1)
                    )
                    + (current[upper_base + xl] & 1)
                    + (current[upper_base + xr] & 1)
                    + (current[lower_base + xl] & 1)
                    + (current[lower_base + xr] & 1)
                )

                index = base + x
                state = current[index]

                if state == 1:
                    if survive[weight]:
                        new[index] = 1
                        alive_count += 1
                    else:
                        new[index] = 2
                        scar_count += 1
                elif state == 0:
                    if birth[weight]:
                        new[index] = 1
                        alive_count += 1

        old = new
        step += 1
        counts.append((alive_count, scar_count))

        if seen is not None:
            key = bytes(old)
            previous = seen.get(key)
            if previous is not None:
                cycle = counts[previous:step]
                cycle_length = len(cycle)
                remaining = gens - step
                full_cycles, rest = divmod(remaining, cycle_length)

                if full_cycles:
                    counts.extend(cycle * full_cycles)
                    step += full_cycles * cycle_length

                seen = None
            else:
                seen[key] = step
                if len(seen) > max_seen:
                    seen = None

    return old, counts


def write_output(width, height, old, counts):
    output = bytearray()

    for generation, (alive_count, scar_count) in enumerate(counts, 1):
        output.extend(str(generation).encode())
        output.append(32)
        output.extend(str(alive_count).encode())
        output.append(32)
        output.extend(str(scar_count).encode())
        output.append(10)

    for y in range(height):
        base = y * width
        output.extend(old[base:base + width].translate(TRANS_OUT))
        output.append(10)

    sys.stdout.buffer.write(output)


def main():
    if len(sys.argv) != 3:
        fail()

    birth, survive = parse_rule(sys.argv[1])
    gens = parse_gens(sys.argv[2])
    width, height, old = read_grid()
    old, counts = simulate(width, height, old, gens, birth, survive)
    write_output(width, height, old, counts)


if __name__ == "__main__":
    main()
