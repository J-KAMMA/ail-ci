import sys
import struct


def pack(data):
    n = len(data)
    out = bytearray()
    out += b'EP1'
    out += struct.pack('<I', n)

    pos_map = {}
    L = bytearray()
    i = 0

    while i < n:
        best_m = 0
        best_p = -1

        if i + 4 <= n:
            key = data[i:i + 4]
            lst = pos_map.get(key)
            if lst:
                limit = i - 65535
                maxm = 131
                if n - i < maxm:
                    maxm = n - i
                cnt = 0
                idx = len(lst) - 1
                while idx >= 0:
                    p = lst[idx]
                    if p < limit:
                        break
                    m = 4
                    while m < maxm and data[p + m] == data[i + m]:
                        m += 1
                    if m > best_m or (m == best_m and p > best_p):
                        best_m = m
                        best_p = p
                    cnt += 1
                    if cnt == 8:
                        break
                    idx -= 1

        if best_m >= 4:
            if L:
                out.append(len(L) - 1)
                out += L
                L.clear()
            dist = i - best_p
            out.append(0x80 + best_m - 4)
            out.append((dist >> 8) & 0xFF)
            out.append(dist & 0xFF)
            end = i + best_m
            j = i
            while j < end:
                if j + 4 <= n:
                    k = data[j:j + 4]
                    l = pos_map.get(k)
                    if l is None:
                        pos_map[k] = [j]
                    else:
                        l.append(j)
                j += 1
            i = end
        else:
            L.append(data[i])
            if len(L) == 128:
                out.append(127)
                out += L
                L.clear()
            if i + 4 <= n:
                k = data[i:i + 4]
                l = pos_map.get(k)
                if l is None:
                    pos_map[k] = [i]
                else:
                    l.append(i)
            i += 1

    if L:
        out.append(len(L) - 1)
        out += L

    h = 0
    for b in data:
        h = (h * 257 + b + 1) & 0xFFFFFFFF
    out += struct.pack('<I', h)
    return bytes(out)


def unpack(data):
    dlen = len(data)
    if dlen < 3:
        return None
    if data[0:3] != b'EP1':
        return None
    if dlen < 7:
        return None
    n = int.from_bytes(data[3:7], 'little')
    pos = 7
    out = bytearray()

    while len(out) < n:
        if pos >= dlen:
            return None
        c = data[pos]
        pos += 1
        if c < 0x80:
            k = c + 1
            if pos + k > dlen:
                return None
            if len(out) + k > n:
                return None
            out += data[pos:pos + k]
            pos += k
        else:
            if pos + 2 > dlen:
                return None
            dist = (data[pos] << 8) | data[pos + 1]
            pos += 2
            length = c - 0x80 + 4
            if dist == 0 or dist > len(out):
                return None
            if len(out) + length > n:
                return None
            for _ in range(length):
                out.append(out[len(out) - dist])

    if pos + 4 != dlen:
        return None

    h = 0
    for b in out:
        h = (h * 257 + b + 1) & 0xFFFFFFFF
    stored = int.from_bytes(data[pos:pos + 4], 'little')
    if stored != h:
        return None
    return bytes(out)


def main():
    if len(sys.argv) != 2:
        sys.exit(1)
    cmd = sys.argv[1]
    if cmd == 'pack':
        data = sys.stdin.buffer.read()
        out = pack(data)
        sys.stdout.buffer.write(out)
        sys.stdout.buffer.flush()
        sys.exit(0)
    elif cmd == 'unpack':
        data = sys.stdin.buffer.read()
        res = unpack(data)
        if res is None:
            sys.exit(2)
        sys.stdout.buffer.write(res)
        sys.stdout.buffer.flush()
        sys.exit(0)
    else:
        sys.exit(1)


main()
