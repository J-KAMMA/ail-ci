import sys


def code_value(c: str) -> int:
    if c >= "0" and c <= "9":
        return ord(c) - 48
    if c == "A":
        return 10
    if c == "B":
        return 11
    if c == "C":
        return 12
    return -1


def parse_rule(rule: str) -> tuple[int, int]:
    n: int = len(rule)
    if n < 3:
        return (-1, -1)
    if rule[0] != "B":
        return (-1, -1)
    i: int = 1
    bmask: int = 0
    last: int = -1
    while i < n and rule[i] != "/":
        rc: str = rule[i]
        v: int = code_value(rc)
        if v < 0 or v <= last:
            return (-1, -1)
        bmask = bmask | (1 << v)
        last = v
        i += 1
    if i >= n or rule[i] != "/":
        return (-1, -1)
    i += 1
    if i >= n or rule[i] != "S":
        return (-1, -1)
    i += 1
    smask: int = 0
    last = -1
    while i < n:
        rc = rule[i]
        v = code_value(rc)
        if v < 0 or v <= last:
            return (-1, -1)
        smask = smask | (1 << v)
        last = v
        i += 1
    return (bmask, smask)


def parse_gens(s: str) -> int:
    n: int = len(s)
    if n == 0:
        return -1
    i: int = 0
    while i < n:
        gc: str = s[i]
        if gc < "0" or gc > "9":
            return -1
        i += 1
    j: int = 0
    while j < n and s[j] == "0":
        j += 1
    if j == n:
        return 0
    if n - j > 6:
        return -1
    value: int = 0
    k: int = j
    while k < n:
        value = value * 10 + (ord(s[k]) - 48)
        k += 1
    if value > 100000:
        return -1
    return value


def parse_dim(b: bytes) -> int:
    n: int = len(b)
    if n < 1 or n > 4:
        return -1
    if b[0] == 48:
        return -1
    value: int = 0
    i: int = 0
    while i < n:
        dc: int = b[i]
        if dc < 48 or dc > 57:
            return -1
        value = value * 10 + (dc - 48)
        i += 1
    if value < 1 or value > 4096:
        return -1
    return value


def parse_input(data: bytes) -> tuple[int, int, bytes]:
    n: int = len(data)
    nl: int = -1
    i: int = 0
    while i < n:
        if data[i] == 10:
            nl = i
            break
        i += 1
    if nl < 0:
        return (-1, -1, b"")
    header: bytes = data[0:nl]
    sp: int = -1
    spaces: int = 0
    i = 0
    while i < len(header):
        if header[i] == 32:
            spaces += 1
            sp = i
        i += 1
    if spaces != 1:
        return (-1, -1, b"")
    if sp <= 0 or sp >= len(header) - 1:
        return (-1, -1, b"")
    w: int = parse_dim(header[0:sp])
    h: int = parse_dim(header[sp + 1:len(header)])
    if w < 0 or h < 0:
        return (-1, -1, b"")
    rows: list[bytes] = []
    pos: int = nl + 1
    y: int = 0
    while y < h:
        if pos + w > n:
            return (-1, -1, b"")
        grid_row: bytes = data[pos:pos + w]
        x: int = 0
        while x < w:
            pc: int = grid_row[x]
            if pc != 46 and pc != 111:
                return (-1, -1, b"")
            x += 1
        rows.append(grid_row)
        pos += w
        if y < h - 1:
            if pos >= n or data[pos] != 10:
                return (-1, -1, b"")
            pos += 1
        y += 1
    if pos == n:
        pass
    elif data[pos] == 10 and pos + 1 == n:
        pos += 1
    else:
        return (-1, -1, b"")
    grid: bytes = b"".join(rows)
    return (w, h, grid)


def simulate(w: int, h: int, gens: int, bmask: int, smask: int, grid: bytes) -> list[str]:
    out: list[str] = []
    old: bytes = grid
    n: int = w * h
    g: int = 0
    while g < gens:
        new: list[int] = [0] * n
        alive: int = 0
        scars: int = 0
        y: int = 0
        while y < h:
            row_start: int = y * w
            up_row: int = ((y - 1) % h) * w
            down_row: int = ((y + 1) % h) * w
            x: int = 0
            while x < w:
                xm1: int = x - 1
                if xm1 < 0:
                    xm1 = w - 1
                xp1: int = x + 1
                if xp1 >= w:
                    xp1 = 0
                idx: int = row_start + x
                weight: int = 0
                if old[up_row + x] == 111:
                    weight += 2
                if old[down_row + x] == 111:
                    weight += 2
                if old[row_start + xm1] == 111:
                    weight += 2
                if old[row_start + xp1] == 111:
                    weight += 2
                if old[up_row + xm1] == 111:
                    weight += 1
                if old[up_row + xp1] == 111:
                    weight += 1
                if old[down_row + xm1] == 111:
                    weight += 1
                if old[down_row + xp1] == 111:
                    weight += 1
                state: int = old[idx]
                if state == 111:
                    if ((smask >> weight) & 1) != 0:
                        new[idx] = 111
                        alive += 1
                    else:
                        new[idx] = 120
                        scars += 1
                elif state == 46:
                    if ((bmask >> weight) & 1) != 0:
                        new[idx] = 111
                        alive += 1
                    else:
                        new[idx] = 46
                else:
                    new[idx] = 46
                x += 1
            y += 1
        old = bytes(new)
        g += 1
        out.append(str(g) + " " + str(alive) + " " + str(scars))
    y = 0
    while y < h:
        start: int = y * w
        out.append(old[start:start + w].decode("ascii"))
        y += 1
    return out


def main() -> int:
    if len(sys.argv) != 3:
        return 1
    rule: str = sys.argv[1]
    gens_text: str = sys.argv[2]
    parsed: tuple[int, int] = parse_rule(rule)
    bmask: int = parsed[0]
    smask: int = parsed[1]
    if bmask < 0:
        return 1
    gens: int = parse_gens(gens_text)
    if gens < 0:
        return 1
    data: bytes = sys.stdin.buffer.read()
    parsed_grid: tuple[int, int, bytes] = parse_input(data)
    w: int = parsed_grid[0]
    h: int = parsed_grid[1]
    grid: bytes = parsed_grid[2]
    if w < 0 or h < 0:
        return 1
    lines: list[str] = simulate(w, h, gens, bmask, smask, grid)
    output: str = "\n".join(lines) + "\n"
    sys.stdout.write(output)
    return 0


sys.exit(main())
