import sys


def hash32(data):
    h = 0
    for b in data:
        h = (h * 257 + b + 1) & 0xFFFFFFFF
    return h


def emit_literal(out, lit):
    k = len(lit)
    out.append(k - 1)
    out.extend(lit)


def pack(data):
    n = len(data)
    out = bytearray(b'EP1')
    out.extend(n.to_bytes(4, 'little'))
    lit = bytearray()
    index = {}
    ix = 0
    i = 0
    while i < n:
        # index all positions p < i that have 4 bytes available
        while ix < i:
            if ix + 4 <= n:
                key = data[ix:ix + 4]
                lst = index.get(key)
                if lst is None:
                    index[key] = [ix]
                else:
                    lst.append(ix)
            ix += 1
        best_m = 0
        best_p = -1
        if i + 4 <= n:
            key = data[i:i + 4]
            lst = index.get(key)
            if lst is not None:
                cap = min(131, n - i)
                cnt = 0
                j = len(lst) - 1
                while j >= 0 and cnt < 8:
                    p = lst[j]
                    if i - p > 65535:
                        break
                    cnt += 1
                    m = 4
                    while m < cap and data[p + m] == data[i + m]:
                        m += 1
                    if m > best_m:
                        best_m = m
                        best_p = p
                    j -= 1
        if best_p >= 0:
            if len(lit) > 0:
                emit_literal(out, lit)
                lit = bytearray()
            d = i - best_p
            out.append(0x80 + best_m - 4)
            out.append((d >> 8) & 0xFF)
            out.append(d & 0xFF)
            i += best_m
        else:
            lit.append(data[i])
            if len(lit) == 128:
                emit_literal(out, lit)
                lit = bytearray()
            i += 1
    if len(lit) > 0:
        emit_literal(out, lit)
    out.extend(hash32(data).to_bytes(4, 'little'))
    return bytes(out)


def unpack(data):
    L = len(data)
    if L < 3 or data[0:3] != b'EP1':
        return None
    if L < 7:
        return None
    n = int.from_bytes(data[3:7], 'little')
    pos = 7
    out = bytearray()
    while len(out) < n:
        if pos >= L:
            return None
        c = data[pos]
        pos += 1
        if c < 0x80:
            k = c + 1
            if pos + k > L:
                return None
            if len(out) + k > n:
                return None
            out.extend(data[pos:pos + k])
            pos += k
        else:
            if pos + 2 > L:
                return None
            dist = (data[pos] << 8) | data[pos + 1]
            pos += 2
            if dist == 0 or dist > len(out):
                return None
            ln = c - 0x80 + 4
            if len(out) + ln > n:
                return None
            for _ in range(ln):
                out.append(out[-dist])
    if L - pos < 4:
        return None
    h = int.from_bytes(data[pos:pos + 4], 'little')
    pos += 4
    if pos != L:
        return None
    if h != hash32(out):
        return None
    return bytes(out)


def main():
    if len(sys.argv) != 2:
        sys.exit(1)
    mode = sys.argv[1]
    if mode == 'pack':
        data = sys.stdin.buffer.read()
        res = pack(data)
    elif mode == 'unpack':
        data = sys.stdin.buffer.read()
        res = unpack(data)
        if res is None:
            sys.exit(2)
    else:
        sys.exit(1)
    sys.stdout.buffer.write(res)
    sys.stdout.buffer.flush()
    sys.exit(0)


main()
