import sys
from collections import deque


MAGIC = b"EP1"


def pack(data: bytes) -> bytes:
    n = len(data)
    out = bytearray(MAGIC)
    out += n.to_bytes(4, "little")

    candidates = {}
    order = deque()
    next_add = 0
    literal = bytearray()
    i = 0

    while i < n:
        while next_add < i:
            p = next_add
            if p + 4 <= n:
                key = data[p:p + 4]
                dq = candidates.get(key)
                if dq is None:
                    dq = deque()
                    candidates[key] = dq
                dq.append(p)
                order.append((p, key))
            next_add += 1

        cutoff = i - 65535
        while order and order[0][0] < cutoff:
            p, key = order.popleft()
            dq = candidates[key]
            if dq and dq[0] == p:
                dq.popleft()
            if not dq:
                del candidates[key]

        if i + 4 <= n:
            key = data[i:i + 4]
            dq = candidates.get(key)
            if dq:
                max_m = min(131, n - i)
                best_m = -1
                best_p = -1
                count = min(8, len(dq))

                for idx in range(len(dq) - 1, len(dq) - 1 - count, -1):
                    p = dq[idx]
                    m = 4
                    while m < max_m and data[p + m] == data[i + m]:
                        m += 1
                    if m > best_m or (m == best_m and p > best_p):
                        best_m = m
                        best_p = p

                if literal:
                    out.append(len(literal) - 1)
                    out.extend(literal)
                    literal.clear()

                out.append(0x80 + (best_m - 4))
                dist = i - best_p
                out.append((dist >> 8) & 0xFF)
                out.append(dist & 0xFF)
                i += best_m
                continue

        literal.append(data[i])
        if len(literal) == 128:
            out.append(127)
            out.extend(literal)
            literal.clear()
        i += 1

    if literal:
        out.append(len(literal) - 1)
        out.extend(literal)

    h = 0
    for b in data:
        h = (h * 257 + b + 1) & 0xFFFFFFFF
    out += h.to_bytes(4, "little")

    return bytes(out)


def unpack(data: bytes):
    if len(data) < 3 or data[:3] != MAGIC:
        return None
    if len(data) < 7:
        return None

    n = int.from_bytes(data[3:7], "little")
    pos = 7
    out = bytearray()

    while len(out) < n:
        if pos >= len(data):
            return None

        c = data[pos]
        pos += 1

        if c < 0x80:
            length = c + 1
            if pos + length > len(data):
                return None
            if len(out) + length > n:
                return None
            out.extend(data[pos:pos + length])
            pos += length
        else:
            if pos + 2 > len(data):
                return None
            dist = (data[pos] << 8) | data[pos + 1]
            pos += 2
            length = (c - 0x80) + 4

            if dist == 0 or dist > len(out):
                return None
            if len(out) + length > n:
                return None

            for _ in range(length):
                out.append(out[-dist])

    if len(data) - pos != 4:
        return None

    expected = int.from_bytes(data[pos:pos + 4], "little")
    h = 0
    for b in out:
        h = (h * 257 + b + 1) & 0xFFFFFFFF

    if h != expected:
        return None

    return bytes(out)


def main() -> int:
    args = sys.argv[1:]

    if len(args) != 1 or args[0] not in ("pack", "unpack"):
        return 1

    data = sys.stdin.buffer.read()

    if args[0] == "pack":
        sys.stdout.buffer.write(pack(data))
        return 0

    result = unpack(data)
    if result is None:
        return 2

    sys.stdout.buffer.write(result)
    return 0


if __name__ == "__main__":
    sys.exit(main())
