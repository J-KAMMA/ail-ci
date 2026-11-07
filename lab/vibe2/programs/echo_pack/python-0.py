import sys
from collections import deque


MASK = 0xFFFFFFFF


def pack(data: bytes) -> bytes:
    n = len(data)
    out = bytearray(b"EP1")
    out.extend(n.to_bytes(4, "little"))

    literals = bytearray()

    def flush_literals():
        if literals:
            out.append(len(literals) - 1)
            out.extend(literals)
            literals.clear()

    index = {}
    expiring = deque()
    last_added = 0
    i = 0

    while i < n:
        limit = i - 65535
        while expiring and expiring[0][0] < limit:
            p, key = expiring.popleft()
            dq = index.get(key)
            if dq is not None and dq and dq[0] == p:
                dq.popleft()
                if not dq:
                    del index[key]

        while last_added < i:
            p = last_added
            if p + 4 <= n:
                key = (data[p] << 24) | (data[p + 1] << 16) | (data[p + 2] << 8) | data[p + 3]
                dq = index.get(key)
                if dq is None:
                    dq = deque(maxlen=8)
                    index[key] = dq
                dq.append(p)
                expiring.append((p, key))
            last_added += 1

        best_length = 0
        best_position = -1

        if i + 4 <= n:
            key = (data[i] << 24) | (data[i + 1] << 16) | (data[i + 2] << 8) | data[i + 3]
            dq = index.get(key)
            if dq:
                max_length = n - i
                if max_length > 131:
                    max_length = 131

                for j in range(len(dq) - 1, -1, -1):
                    p = dq[j]
                    length = 4
                    while length < max_length and data[p + length] == data[i + length]:
                        length += 1

                    if length > best_length or (length == best_length and p > best_position):
                        best_length = length
                        best_position = p

        if best_length:
            flush_literals()
            out.append(0x80 + best_length - 4)
            distance = i - best_position
            out.append((distance >> 8) & 0xFF)
            out.append(distance & 0xFF)
            i += best_length
        else:
            literals.append(data[i])
            if len(literals) == 128:
                flush_literals()
            i += 1

    flush_literals()

    h = 0
    for b in data:
        h = (h * 257 + b + 1) & MASK

    out.extend(h.to_bytes(4, "little"))
    return bytes(out)


def unpack(data: bytes):
    if len(data) < 3 or data[:3] != b"EP1":
        return 2, None
    if len(data) < 7:
        return 2, None

    n = int.from_bytes(data[3:7], "little")
    out = bytearray()
    pos = 7
    total = len(data)

    while len(out) < n:
        if pos >= total:
            return 2, None

        c = data[pos]
        pos += 1

        if c < 0x80:
            length = c + 1
            if len(out) + length > n:
                return 2, None
            if pos + length > total:
                return 2, None
            out.extend(data[pos:pos + length])
            pos += length
        else:
            if pos + 2 > total:
                return 2, None
            distance = (data[pos] << 8) | data[pos + 1]
            pos += 2

            if distance == 0 or distance > len(out):
                return 2, None

            length = (c - 0x80) + 4
            if len(out) + length > n:
                return 2, None

            for _ in range(length):
                out.append(out[-distance])

    if total - pos != 4:
        return 2, None

    expected_hash = int.from_bytes(data[pos:pos + 4], "little")

    h = 0
    for b in out:
        h = (h * 257 + b + 1) & MASK

    if h != expected_hash:
        return 2, None

    return 0, bytes(out)


def main() -> int:
    if len(sys.argv) != 2 or sys.argv[1] not in ("pack", "unpack"):
        return 1

    data = sys.stdin.buffer.read()

    if sys.argv[1] == "pack":
        sys.stdout.buffer.write(pack(data))
        return 0

    status, result = unpack(data)
    if status != 0:
        return 2

    sys.stdout.buffer.write(result)
    return 0


if __name__ == "__main__":
    sys.exit(main())
