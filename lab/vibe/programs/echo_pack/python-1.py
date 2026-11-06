import sys
from collections import deque

MAGIC = b"EP1"
MASK = 0xFFFFFFFF


def compute_hash(data):
    h = 0
    for b in data:
        h = (h * 257 + b + 1) & MASK
    return h


def key4(data, p):
    return (
        data[p]
        | (data[p + 1] << 8)
        | (data[p + 2] << 16)
        | (data[p + 3] << 24)
    )


def pack():
    data = sys.stdin.buffer.read()
    n = len(data)

    out = bytearray(MAGIC)
    out += (n & MASK).to_bytes(4, "little")

    index = {}
    window = deque()
    next_add = 0

    literals = bytearray()
    i = 0

    while i < n:
        while next_add < i:
            p = next_add
            if p + 4 <= n:
                k = key4(data, p)
                dq = index.get(k)
                if dq is None:
                    dq = deque()
                    index[k] = dq
                dq.append(p)
                window.append((p, k))
            next_add += 1

        low = i - 65535
        while window and window[0][0] < low:
            p, k = window.popleft()
            dq = index[k]
            dq.popleft()
            if not dq:
                del index[k]

        best_m = 0
        best_p = -1

        if i + 4 <= n:
            k = key4(data, i)
            dq = index.get(k)

            if dq:
                max_len = min(131, n - i)
                considered = 0

                for p in reversed(dq):
                    m = 4
                    while m < max_len and data[p + m] == data[i + m]:
                        m += 1

                    if m > best_m:
                        best_m = m
                        best_p = p

                    considered += 1
                    if considered == 8:
                        break

        if best_m >= 4:
            if literals:
                out.append(len(literals) - 1)
                out.extend(literals)
                literals.clear()

            dist = i - best_p
            out.append(0x80 + (best_m - 4))
            out.append((dist >> 8) & 0xFF)
            out.append(dist & 0xFF)
            i += best_m
        else:
            literals.append(data[i])
            if len(literals) == 128:
                out.append(127)
                out.extend(literals)
                literals.clear()
            i += 1

    if literals:
        out.append(len(literals) - 1)
        out.extend(literals)

    out += compute_hash(data).to_bytes(4, "little")
    sys.stdout.buffer.write(out)


def unpack():
    data = sys.stdin.buffer.read()

    if len(data) < 7 or data[:3] != MAGIC:
        sys.exit(2)

    n = int.from_bytes(data[3:7], "little")
    output = bytearray()

    pos = 7
    end = len(data)

    while len(output) < n:
        if pos >= end:
            sys.exit(2)

        c = data[pos]
        pos += 1

        if c <= 0x7F:
            length = c + 1

            if pos + length > end:
                sys.exit(2)
            if len(output) + length > n:
                sys.exit(2)

            output.extend(data[pos:pos + length])
            pos += length
        else:
            length = (c - 0x80) + 4

            if pos + 2 > end:
                sys.exit(2)

            dist = (data[pos] << 8) | data[pos + 1]
            pos += 2

            if dist == 0 or dist > len(output):
                sys.exit(2)
            if len(output) + length > n:
                sys.exit(2)

            if dist >= length:
                start = len(output) - dist
                output.extend(output[start:start + length])
            else:
                pattern = output[-dist:]
                repetitions = (length + dist - 1) // dist
                output.extend((pattern * repetitions)[:length])

    if pos + 4 > end:
        sys.exit(2)

    expected_hash = int.from_bytes(data[pos:pos + 4], "little")
    if expected_hash != compute_hash(output):
        sys.exit(2)

    pos += 4
    if pos != end:
        sys.exit(2)

    sys.stdout.buffer.write(output)


def main():
    args = sys.argv[1:]

    if len(args) != 1 or args[0] not in ("pack", "unpack"):
        sys.exit(1)

    if args[0] == "pack":
        pack()
    else:
        unpack()


if __name__ == "__main__":
    main()
