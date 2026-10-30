"""Reference implementation of echo_pack (see spec.md): reference.py pack|unpack < in > out

pack keeps, for every 4-byte key, only its 8 most recent positions: the spec considers only the
8 largest earlier positions with that key, so older ones can never be candidates.
"""
import sys
from operator import mul

M32 = 0xFFFFFFFF
CHUNK = 4096


def powers(k):
    p = [1] * k
    for j in range(k - 2, -1, -1):
        p[j] = p[j + 1] * 257 & M32
    return p


FULL = powers(CHUNK)
FULL_SUM = sum(FULL)
FULL_MUL = pow(257, CHUNK, 1 << 32)


def ep_hash(data):
    """h = (h * 257 + b + 1) mod 2^32 over data, chunk by chunk."""
    h = 0
    n = len(data)
    i = 0
    while i + CHUNK <= n:
        h = (h * FULL_MUL + sum(map(mul, data[i:i + CHUNK], FULL)) + FULL_SUM) & M32
        i += CHUNK
    if i < n:
        k = n - i
        p = powers(k)
        h = (h * pow(257, k, 1 << 32) + sum(map(mul, data[i:], p)) + sum(p)) & M32
    return h


def pack(d):
    n = len(d)
    out = [b'EP1', n.to_bytes(4, 'little')]
    table = {}
    lit = bytearray()
    reg = 0                 # positions < reg are registered in table
    i = 0
    last_key = n - 4        # largest position that has a 4-byte key
    while i < n:
        while reg < i:
            if reg <= last_key:
                key = d[reg:reg + 4]
                lst = table.get(key)
                if lst is None:
                    table[key] = [reg]
                else:
                    lst.append(reg)
                    if len(lst) > 8:
                        del lst[0]
            reg += 1
        best_m = 0
        best_p = -1
        if i <= last_key:
            lst = table.get(d[i:i + 4])
            if lst:
                limit = min(131, n - i)
                for p in reversed(lst):
                    if i - p > 65535:
                        break
                    if d[p:p + limit] == d[i:i + limit]:
                        m = limit
                    else:
                        lo, hi = 4, limit - 1          # d[p:p+lo] equal, d[p:p+hi+1] not
                        while lo < hi:
                            mid = (lo + hi + 1) // 2
                            if d[p:p + mid] == d[i:i + mid]:
                                lo = mid
                            else:
                                hi = mid - 1
                        m = lo
                    if m > best_m:          # positions come largest first: ties keep the larger p
                        best_m = m
                        best_p = p
        if best_m:
            if lit:
                out.append(bytes([len(lit) - 1]) + lit)
                lit = bytearray()
            out.append(bytes([0x80 + best_m - 4]) + (i - best_p).to_bytes(2, 'big'))
            i += best_m
        else:
            lit.append(d[i])
            if len(lit) == 128:
                out.append(bytes([127]) + lit)
                lit = bytearray()
            i += 1
    if lit:
        out.append(bytes([len(lit) - 1]) + lit)
    out.append(ep_hash(d).to_bytes(4, 'little'))
    return b''.join(out)


def unpack(s):
    if len(s) < 7 or s[:3] != b'EP1':
        return None
    n = int.from_bytes(s[3:7], 'little')
    pos = 7
    total = len(s)
    out = bytearray()
    while len(out) < n:
        if pos >= total:
            return None
        c = s[pos]
        pos += 1
        if c < 0x80:
            k = c + 1
            if pos + k > total or len(out) + k > n:
                return None
            out += s[pos:pos + k]
            pos += k
        else:
            if pos + 2 > total:
                return None
            dist = (s[pos] << 8) | s[pos + 1]
            pos += 2
            ln = c - 0x80 + 4
            if dist == 0 or dist > len(out) or len(out) + ln > n:
                return None
            start = len(out) - dist
            if dist >= ln:
                out += out[start:start + ln]
            else:
                for k in range(ln):
                    out.append(out[start + k])
    if total - pos != 4:
        return None
    if int.from_bytes(s[pos:pos + 4], 'little') != ep_hash(out):
        return None
    return bytes(out)


def main(argv):
    if len(argv) != 2 or argv[1] not in ('pack', 'unpack'):
        return 1
    data = sys.stdin.buffer.read()
    if argv[1] == 'pack':
        sys.stdout.buffer.write(pack(data))
        return 0
    result = unpack(data)
    if result is None:
        return 2
    sys.stdout.buffer.write(result)
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv))
