import sys
from collections import deque


def pack():
    data = sys.stdin.buffer.read()
    n = len(data)

    hv = 0
    for b in data:
        hv = (hv * 257 + b + 1) & 0xFFFFFFFF

    out = bytearray(b"EP1")
    out += n.to_bytes(4, "little")

    index = {}
    registered = 0
    lit = bytearray()
    i = 0

    while i < n:
        while registered < i:
            p = registered
            if p + 4 <= n:
                key = data[p:p + 4]
                dq = index.get(key)
                if dq is None:
                    dq = deque(maxlen=8)
                    index[key] = dq
                dq.append(p)
            registered += 1

        if i + 4 <= n:
            key = data[i:i + 4]
            dq = index.get(key)
            best_len = 0
            best_p = -1

            if dq is not None:
                max_len = n - i
                if max_len > 131:
                    max_len = 131

                for p in reversed(dq):
                    if i - p > 65535:
                        break

                    ln = 0
                    while ln < max_len and data[p + ln] == data[i + ln]:
                        ln += 1

                    if ln > best_len:
                        best_len = ln
                        best_p = p

            if best_p >= 0:
                if lit:
                    out.append(len(lit) - 1)
                    out.extend(lit)
                    lit.clear()

                out.append(0x80 + (best_len - 4))
                dist = i - best_p
                out.append((dist >> 8) & 0xFF)
                out.append(dist & 0xFF)

                i += best_len
                continue

        lit.append(data[i])
        if len(lit) == 128:
            out.append(127)
            out.extend(lit)
            lit.clear()

        i += 1

    if lit:
        out.append(len(lit) - 1)
        out.extend(lit)

    out += hv.to_bytes(4, "little")
    sys.stdout.buffer.write(out)
    return 0


def unpack():
    data = sys.stdin.buffer.read()

    if len(data) < 3 or data[:3] != b"EP1":
        return 2

    if len(data) < 7:
        return 2

    n = int.from_bytes(data[3:7], "little")
    out = bytearray()
    pos = 7
    total = len(data)

    while len(out) < n:
        if pos >= total:
            return 2

        c = data[pos]
        pos += 1

        if c < 0x80:
            length = c + 1
            if pos + length > total:
                return 2
            if len(out) + length > n:
                return 2

            out.extend(data[pos:pos + length])
            pos += length
        else:
            if pos + 2 > total:
                return 2

            dist = (data[pos] << 8) | data[pos + 1]
            pos += 2

            length = (c - 0x80) + 4

            if dist == 0 or dist > len(out):
                return 2
            if len(out) + length > n:
                return 2

            for _ in range(length):
                out.append(out[-dist])

    if total - pos != 4:
        return 2

    hv = 0
    for b in out:
        hv = (hv * 257 + b + 1) & 0xFFFFFFFF

    if hv != int.from_bytes(data[pos:pos + 4], "little"):
        return 2

    sys.stdout.buffer.write(out)
    return 0


def main():
    args = sys.argv[1:]

    if len(args) != 1 or args[0] not in ("pack", "unpack"):
        return 1

    if args[0] == "pack":
        return pack()

    return unpack()


if __name__ == "__main__":
    sys.exit(main())
