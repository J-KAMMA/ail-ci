import sys


def pack():
    D = sys.stdin.buffer.read()
    n = len(D)

    out = bytearray(b'EP1')
    out += n.to_bytes(4, 'little')

    h = 0
    for b in D:
        h = (h * 257 + b + 1) & 0xFFFFFFFF

    positions = {}
    L = bytearray()
    i = 0

    while i < n:
        best_m = 0
        best_p = -1

        if i + 4 <= n:
            key = D[i:i + 4]
            lst = positions.get(key)

            if lst:
                limit = n - i
                if limit > 131:
                    limit = 131
                for p in lst[-8:]:
                    if i - p > 65535:
                        continue
                    m = 4
                    while m < limit and D[p + m] == D[i + m]:
                        m += 1
                    if m > best_m or (m == best_m and p > best_p):
                        best_m = m
                        best_p = p

            if lst is None:
                positions[key] = [i]
            else:
                lst.append(i)
                if len(lst) > 8:
                    del lst[0]

        if best_m >= 4:
            if L:
                out.append(len(L) - 1)
                out += L
                L = bytearray()

            out.append(0x80 + best_m - 4)
            dist = i - best_p
            out.append(dist >> 8)
            out.append(dist & 0xFF)

            end = i + best_m
            j = i + 1
            while j < end:
                if j + 4 <= n:
                    k2 = D[j:j + 4]
                    l2 = positions.get(k2)
                    if l2 is None:
                        positions[k2] = [j]
                    else:
                        l2.append(j)
                        if len(l2) > 8:
                            del l2[0]
                j += 1

            i = end
        else:
            L.append(D[i])
            if len(L) == 128:
                out.append(127)
                out += L
                L = bytearray()
            i += 1

    if L:
        out.append(len(L) - 1)
        out += L

    out += h.to_bytes(4, 'little')
    sys.stdout.buffer.write(bytes(out))


def unpack():
    data = sys.stdin.buffer.read()
    total = len(data)

    if total < 3 or data[0:3] != b'EP1':
        sys.exit(2)
    if total < 7:
        sys.exit(2)

    n = int.from_bytes(data[3:7], 'little')
    pos = 7
    out = bytearray()

    while len(out) < n:
        if pos >= total:
            sys.exit(2)
        c = data[pos]
        pos += 1

        if c < 0x80:
            k = c + 1
            if pos + k > total:
                sys.exit(2)
            if len(out) + k > n:
                sys.exit(2)
            out += data[pos:pos + k]
            pos += k
        else:
            if pos + 2 > total:
                sys.exit(2)
            dist = (data[pos] << 8) | data[pos + 1]
            pos += 2
            length = c - 0x80 + 4
            if len(out) + length > n:
                sys.exit(2)
            if dist == 0 or dist > len(out):
                sys.exit(2)
            for _ in range(length):
                out.append(out[len(out) - dist])

    if pos + 4 > total:
        sys.exit(2)
    h = int.from_bytes(data[pos:pos + 4], 'little')
    pos += 4
    if pos != total:
        sys.exit(2)

    hh = 0
    for b in out:
        hh = (hh * 257 + b + 1) & 0xFFFFFFFF
    if hh != h:
        sys.exit(2)

    sys.stdout.buffer.write(bytes(out))


def main():
    if len(sys.argv) != 2:
        sys.exit(1)
    cmd = sys.argv[1]
    if cmd == 'pack':
        pack()
    elif cmd == 'unpack':
        unpack()
    else:
        sys.exit(1)


main()
