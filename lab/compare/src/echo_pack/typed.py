from ail import read_stdin_bytes, write_stdout_bytes
import sys

def hash_of(d: bytes) -> int:
    h = 0
    for b in d:
        h = (h * 257 + b + 1) % 4294967296
    return h

def hash_ba(d: bytearray) -> int:
    h = 0
    for b in d:
        h = (h * 257 + b + 1) % 4294967296
    return h

def flush(out: bytearray, d: bytes, start: int, cnt: int) -> None:
    if cnt > 0:
        out.append(cnt - 1)
        out.extend(d[start:start + cnt])

def pack(d: bytes) -> int:
    n = len(d)
    out = bytearray()
    out.extend(b'EP1')
    out.append(n % 256)
    out.append(n // 256 % 256)
    out.append(n // 65536 % 256)
    out.append(n // 16777216 % 256)
    prev = [-1 for _ in range(n)]
    head: dict[int, int] = {}
    i = 0
    lstart = 0
    lcnt = 0
    while i < n:
        bestlen = 0
        bestp = -1
        if i + 4 <= n:
            key = d[i] * 16777216 + d[i + 1] * 65536 + d[i + 2] * 256 + d[i + 3]
            p = -1
            if key in head:
                p = head[key]
            seen = 0
            maxm = n - i
            if maxm > 131:
                maxm = 131
            while p >= 0 and seen < 8 and (i - p <= 65535):
                m = 4
                while m < maxm and d[p + m] == d[i + m]:
                    m += 1
                if m > bestlen:
                    bestlen = m
                    bestp = p
                seen += 1
                p = prev[p]
        if bestp >= 0:
            flush(out, d, lstart, lcnt)
            lcnt = 0
            out.append(128 + bestlen - 4)
            dist = i - bestp
            out.append(dist // 256)
            out.append(dist % 256)
            e = i + bestlen
            while i < e:
                if i + 4 <= n:
                    k2 = d[i] * 16777216 + d[i + 1] * 65536 + d[i + 2] * 256 + d[i + 3]
                    if k2 in head:
                        prev[i] = head[k2]
                    head[k2] = i
                i += 1
        else:
            if lcnt == 0:
                lstart = i
            lcnt += 1
            if lcnt == 128:
                flush(out, d, lstart, lcnt)
                lcnt = 0
            if i + 4 <= n:
                k3 = d[i] * 16777216 + d[i + 1] * 65536 + d[i + 2] * 256 + d[i + 3]
                if k3 in head:
                    prev[i] = head[k3]
                head[k3] = i
            i += 1
    flush(out, d, lstart, lcnt)
    h = hash_of(d)
    out.append(h % 256)
    out.append(h // 256 % 256)
    out.append(h // 65536 % 256)
    out.append(h // 16777216 % 256)
    write_stdout_bytes(out)
    return 0

def unpack(d: bytes) -> int:
    L = len(d)
    if L < 7:
        return 2
    if d[0] != 69 or d[1] != 80 or d[2] != 49:
        return 2
    n = d[3] + d[4] * 256 + d[5] * 65536 + d[6] * 16777216
    pos = 7
    out = bytearray()
    while len(out) < n:
        if pos >= L:
            return 2
        c = d[pos]
        pos += 1
        if c < 128:
            k = c + 1
            if pos + k > L:
                return 2
            if len(out) + k > n:
                return 2
            out.extend(d[pos:pos + k])
            pos += k
        else:
            if pos + 2 > L:
                return 2
            dist = d[pos] * 256 + d[pos + 1]
            pos += 2
            ln = c - 128 + 4
            if dist == 0 or dist > len(out):
                return 2
            if len(out) + ln > n:
                return 2
            for _ in range(ln):
                out.append(out[len(out) - dist])
    if pos + 4 != L:
        return 2
    want = d[pos] + d[pos + 1] * 256 + d[pos + 2] * 65536 + d[pos + 3] * 16777216
    if hash_ba(out) != want:
        return 2
    write_stdout_bytes(out)
    return 0

def main() -> int:
    if len(sys.argv) != 2:
        return 1
    mode = sys.argv[1]
    if mode == 'pack':
        return pack(read_stdin_bytes(1 << 40))
    if mode == 'unpack':
        return unpack(read_stdin_bytes(1 << 40))
    return 1

if __name__ == "__main__":
    sys.exit(main())
