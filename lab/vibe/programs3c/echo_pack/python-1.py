import sys


def pack(data):
    n = len(data)
    out = bytearray(b'EP1')
    out += n.to_bytes(4, 'little')

    table = {}
    ins = 0
    L = bytearray()

    def emit_lit():
        k = len(L)
        if k:
            out.append(k - 1)
            out.extend(L)
            L.clear()

    i = 0
    while i < n:
        # insert all positions j < i that have 4 bytes available
        while ins < i:
            if ins + 4 <= n:
                table.setdefault(data[ins:ins + 4], []).append(ins)
            ins += 1

        best_m = 0
        best_p = -1
        if i + 4 <= n:
            lst = table.get(data[i:i + 4])
            if lst:
                lim = min(131, n - i)
                cnt = 0
                for idx in range(len(lst) - 1, -1, -1):
                    p = lst[idx]
                    if i - p > 65535:
                        break
                    m = 0
                    while m < lim and data[p + m] == data[i + m]:
                        m += 1
                    # iterating from largest p downward: keep first max
                    if m > best_m:
                        best_m = m
                        best_p = p
                    cnt += 1
                    if cnt == 8:
                        break

        if best_p >= 0:
            emit_lit()
            out.append(0x80 + best_m - 4)
            d = i - best_p
            out.append((d >> 8) & 0xFF)
            out.append(d & 0xFF)
            i += best_m
        else:
            L.append(data[i])
            if len(L) == 128:
                emit_lit()
            i += 1

    emit_lit()

    h = 0
    for b in data:
        h = (h * 257 + b + 1) & 0xFFFFFFFF
    out += h.to_bytes(4, 'little')
    return bytes(out)


def unpack(data):
    def fail():
        sys.exit(2)

    if len(data) < 3 or data[:3] != b'EP1':
        fail()
    if len(data) < 7:
        fail()
    n = int.from_bytes(data[3:7], 'little')
    out = bytearray()
    pos = 7
    while len(out) < n:
        if pos >= len(data):
            fail()
        c = data[pos]
        if c < 0x80:
            k = c + 1
            pos += 1
            if pos + k > len(data):
                fail()
            if len(out) + k > n:
                fail()
            out += data[pos:pos + k]
            pos += k
        else:
            if pos + 3 > len(data):
                fail()
            dist = (data[pos + 1] << 8) | data[pos + 2]
            pos += 3
            length = c - 0x80 + 4
            if dist == 0 or dist > len(out):
                fail()
            if len(out) + length > n:
                fail()
            start = len(out) - dist
            for k in range(length):
                out.append(out[start + k])

    if pos + 4 > len(data):
        fail()
    h = 0
    for b in out:
        h = (h * 257 + b + 1) & 0xFFFFFFFF
    if int.from_bytes(data[pos:pos + 4], 'little') != h:
        fail()
    if pos + 4 != len(data):
        fail()
    return bytes(out)


def main():
    args = sys.argv[1:]
    if len(args) != 1 or args[0] not in ('pack', 'unpack'):
        sys.exit(1)
    data = sys.stdin.buffer.read()
    if args[0] == 'pack':
        result = pack(data)
    else:
        result = unpack(data)
    sys.stdout.buffer.write(result)
    sys.stdout.buffer.flush()
    sys.exit(0)


if __name__ == '__main__':
    main()
