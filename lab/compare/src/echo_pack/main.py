import sys


def hsh(data):
    h = 0
    for b in data:
        h = (h * 257 + b + 1) & 0xFFFFFFFF
    return h


def pack(D):
    n = len(D)
    out = bytearray(b"EP1")
    out += n.to_bytes(4, "little")
    L = bytearray()
    idx = {}
    ins = 0  # next position to insert into index
    i = 0
    while i < n:
        best_m = 0
        best_p = -1
        if i + 4 <= n:
            while ins < i:
                if ins + 4 <= n:
                    idx.setdefault(D[ins:ins + 4], []).append(ins)
                ins += 1
            lst = idx.get(D[i:i + 4])
            if lst:
                lim = min(131, n - i)
                lo = i - 65535
                cnt = 0
                j = len(lst) - 1
                while j >= 0 and cnt < 8:
                    p = lst[j]
                    if p < lo:
                        break
                    cnt += 1
                    j -= 1
                    m = 4
                    while m < lim and D[p + m] == D[i + m]:
                        m += 1
                    if m > best_m:
                        best_m = m
                        best_p = p
        if best_p >= 0:
            if L:
                out.append(len(L) - 1)
                out += L
                L = bytearray()
            out.append(0x80 + best_m - 4)
            out += (i - best_p).to_bytes(2, "big")
            i += best_m
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
    out += hsh(D).to_bytes(4, "little")
    return bytes(out)


def unpack(S):
    if len(S) < 7 or S[:3] != b"EP1":
        return None
    n = int.from_bytes(S[3:7], "little")
    pos = 7
    end = len(S)
    out = bytearray()
    while len(out) < n:
        if pos >= end:
            return None
        c = S[pos]
        pos += 1
        if c < 0x80:
            k = c + 1
            if pos + k > end or len(out) + k > n:
                return None
            out += S[pos:pos + k]
            pos += k
        else:
            if pos + 2 > end:
                return None
            dist = (S[pos] << 8) | S[pos + 1]
            pos += 2
            ln = c - 0x80 + 4
            if dist == 0 or dist > len(out) or len(out) + ln > n:
                return None
            for _ in range(ln):
                out.append(out[-dist])
    if end - pos != 4:
        return None
    if int.from_bytes(S[pos:], "little") != hsh(out):
        return None
    return bytes(out)


def main():
    if len(sys.argv) != 2 or sys.argv[1] not in ("pack", "unpack"):
        return 1
    data = sys.stdin.buffer.read()
    if sys.argv[1] == "pack":
        res = pack(data)
        code = 0
    else:
        res = unpack(data)
        code = 0
        if res is None:
            return 2
    sys.stdout.buffer.write(res)
    sys.stdout.buffer.flush()
    return code


sys.exit(main())
