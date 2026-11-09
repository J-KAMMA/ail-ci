import sys
import struct


def pack(data: bytes) -> bytes:
    D = data
    n = len(D)
    out = bytearray(b"EP1" + struct.pack("<I", n))
    table = {}
    ins = 0
    L = bytearray()
    i = 0
    while i < n:
        # Insert all positions p < i that can start a 4-byte key.
        while ins < i:
            if ins + 4 <= n:
                table.setdefault(D[ins:ins + 4], []).append(ins)
            ins += 1

        best_m = 0
        best_p = -1
        if i + 4 <= n:
            lst = table.get(D[i:i + 4], [])
            cands = []
            for p in reversed(lst):
                if i - p > 65535:
                    break
                cands.append(p)
                if len(cands) == 8:
                    break
            mx = min(131, n - i)
            for p in cands:
                m = 0
                while m < mx and D[p + m] == D[i + m]:
                    m += 1
                if m > best_m:
                    best_m = m
                    best_p = p

        if best_m > 0:
            if L:
                out.append(len(L) - 1)
                out += L
                L = bytearray()
            d = i - best_p
            out.append(0x80 + best_m - 4)
            out.append((d >> 8) & 0xFF)
            out.append(d & 0xFF)
            i += best_m
        else:
            L.append(D[i])
            i += 1
            if len(L) == 128:
                out.append(127)
                out += L
                L = bytearray()

    if L:
        out.append(len(L) - 1)
        out += L

    h = 0
    for b in D:
        h = (h * 257 + b + 1) & 0xFFFFFFFF
    out += struct.pack("<I", h)
    return bytes(out)


class BadStream(Exception):
    pass


def unpack(data: bytes) -> bytes:
    if len(data) < 3 or data[:3] != b"EP1":
        raise BadStream()
    if len(data) < 7:
        raise BadStream()
    n = struct.unpack("<I", data[3:7])[0]
    pos = 7
    total = len(data)
    out = bytearray()
    while len(out) < n:
        if pos >= total:
            raise BadStream()
        c = data[pos]
        pos += 1
        if c <= 0x7F:
            k = c + 1
            if pos + k > total:
                raise BadStream()
            if len(out) + k > n:
                raise BadStream()
            out += data[pos:pos + k]
            pos += k
        else:
            if pos + 2 > total:
                raise BadStream()
            dist = (data[pos] << 8) | data[pos + 1]
            pos += 2
            length = (c - 0x80) + 4
            if dist == 0 or dist > len(out):
                raise BadStream()
            if len(out) + length > n:
                raise BadStream()
            start = len(out) - dist
            for k in range(length):
                out.append(out[start + k])

    if pos + 4 > total:
        raise BadStream()
    stored = struct.unpack("<I", data[pos:pos + 4])[0]
    pos += 4
    h = 0
    for b in out:
        h = (h * 257 + b + 1) & 0xFFFFFFFF
    if h != stored:
        raise BadStream()
    if pos != total:
        raise BadStream()
    return bytes(out)


def main() -> int:
    args = sys.argv[1:]
    if len(args) != 1 or args[0] not in ("pack", "unpack"):
        return 1
    data = sys.stdin.buffer.read()
    if args[0] == "pack":
        result = pack(data)
    else:
        try:
            result = unpack(data)
        except BadStream:
            return 2
    sys.stdout.buffer.write(result)
    sys.stdout.buffer.flush()
    return 0


if __name__ == "__main__":
    sys.exit(main())
