import sys


def fail():
    sys.exit(2)


def pack(data):
    n = len(data)
    out = bytearray(b'EP1')
    out.append(n & 255)
    out.append((n >> 8) & 255)
    out.append((n >> 16) & 255)
    out.append((n >> 24) & 255)
    table = {}
    ins = 0
    L = bytearray()
    i = 0
    while i < n:
        # insert every position p < i that can start a 4-byte window
        while ins < i and ins + 4 <= n:
            key = data[ins:ins + 4]
            lst = table.get(key)
            if lst is None:
                table[key] = [ins]
            else:
                lst.append(ins)
            ins += 1
        best_m = 0
        best_p = -1
        if i + 4 <= n:
            lst = table.get(data[i:i + 4])
            if lst is not None:
                limit = min(131, n - i)
                cnt = 0
                idx = len(lst) - 1
                while idx >= 0 and cnt < 8:
                    p = lst[idx]
                    if p < i - 65535:
                        break
                    cnt += 1
                    m = 0
                    while m < limit and data[p + m] == data[i + m]:
                        m += 1
                    if m > best_m:
                        best_m = m
                        best_p = p
                    idx -= 1
        if best_p >= 0:
            if len(L) > 0:
                out.append(len(L) - 1)
                out.extend(L)
                L.clear()
            dist = i - best_p
            out.append(0x80 + best_m - 4)
            out.append((dist >> 8) & 255)
            out.append(dist & 255)
            i += best_m
        else:
            L.append(data[i])
            if len(L) == 128:
                out.append(127)
                out.extend(L)
                L.clear()
            i += 1
    if len(L) > 0:
        out.append(len(L) - 1)
        out.extend(L)
        L.clear()
    h = 0
    for b in data:
        h = (h * 257 + b + 1) % 4294967296
    out.append(h & 255)
    out.append((h >> 8) & 255)
    out.append((h >> 16) & 255)
    out.append((h >> 24) & 255)
    return out


def unpack(data):
    nd = len(data)
    if nd < 3 or data[0:3] != b'EP1':
        fail()
    if nd < 7:
        fail()
    n = data[3] | (data[4] << 8) | (data[5] << 16) | (data[6] << 24)
    out = bytearray()
    pos = 7
    while len(out) < n:
        if pos >= nd:
            fail()
        c = data[pos]
        if c < 0x80:
            k = c + 1
            if pos + 1 + k > nd:
                fail()
            if len(out) + k > n:
                fail()
            out.extend(data[pos + 1:pos + 1 + k])
            pos += 1 + k
        else:
            if pos + 3 > nd:
                fail()
            dist = (data[pos + 1] << 8) | data[pos + 2]
            ln = c - 0x80 + 4
            if dist == 0 or dist > len(out):
                fail()
            if len(out) + ln > n:
                fail()
            for _ in range(ln):
                out.append(out[-dist])
            pos += 3
    if pos + 4 > nd:
        fail()
    stored = data[pos] | (data[pos + 1] << 8) | (data[pos + 2] << 16) | (data[pos + 3] << 24)
    h = 0
    for b in out:
        h = (h * 257 + b + 1) % 4294967296
    if h != stored:
        fail()
    pos += 4
    if pos != nd:
        fail()
    return out


def main():
    args = sys.argv[1:]
    if len(args) != 1 or args[0] not in ('pack', 'unpack'):
        sys.exit(1)
    data = sys.stdin.buffer.read()
    if args[0] == 'pack':
        res = pack(data)
    else:
        res = unpack(data)
    sys.stdout.buffer.write(bytes(res))
    sys.stdout.buffer.flush()
    sys.exit(0)


main()
