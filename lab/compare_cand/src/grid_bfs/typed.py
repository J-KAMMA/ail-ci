from ail import read_stdin_bytes
import sys

WALL: int = 35
OPEN: int = 46


def num(tok: bytes) -> int:
    n = len(tok)
    if n == 0:
        return -1
    v = 0
    i = 0
    while i < n:
        c = tok[i]
        if c < 48 or c > 57:
            return -1
        v = v * 10 + c - 48
        if v > 100000000:
            return -1
        i += 1
    return v


def main() -> int:
    data = read_stdin_bytes(1 << 30)
    if len(data) == 0:
        return 2
    lines = data.split(b'\n')
    nl = len(lines)
    if nl > 0 and lines[nl - 1] == b'':
        nl -= 1
    if nl < 1:
        return 2
    hdr = lines[0].split(b' ')
    if len(hdr) != 3:
        return 2
    H = num(hdr[0])
    W = num(hdr[1])
    Q = num(hdr[2])
    if H < 1 or H > 2000 or W < 1 or W > 2000 or Q < 0 or Q > 20:
        return 2
    if nl != 1 + H + Q:
        return 2
    i = 1
    while i <= H:
        row = lines[i]
        if len(row) != W:
            return 2
        j = 0
        while j < W:
            c = row[j]
            if c != OPEN and c != WALL:
                return 2
            j += 1
        i += 1
    flat = b''.join(lines[1:1 + H])
    qr: list[int] = []
    qc: list[int] = []
    qr2: list[int] = []
    qc2: list[int] = []
    i = 1 + H
    k = 0
    while k < Q:
        parts = lines[i].split(b' ')
        if len(parts) != 4:
            return 2
        r1 = num(parts[0])
        c1 = num(parts[1])
        r2 = num(parts[2])
        c2 = num(parts[3])
        if (r1 < 0 or r1 >= H or c1 < 0 or c1 >= W
                or r2 < 0 or r2 >= H or c2 < 0 or c2 >= W):
            return 2
        qr.append(r1)
        qc.append(c1)
        qr2.append(r2)
        qc2.append(c2)
        i += 1
        k += 1
    n = H * W
    total = 0
    qi = 0
    while qi < Q:
        r1 = qr[qi]
        c1 = qc[qi]
        r2 = qr2[qi]
        c2 = qc2[qi]
        s = r1 * W + c1
        t = r2 * W + c2
        if flat[s] == WALL or flat[t] == WALL:
            print(f'dist -1 seen 0')
            qi += 1
            continue
        dist: list[int] = [-1] * n
        queue: list[int] = [0] * n
        head = 0
        tail = 1
        queue[0] = s
        dist[s] = 0
        seen = 0
        d = -1
        while head < tail:
            v = queue[head]
            head += 1
            seen += 1
            if v == t:
                d = dist[v]
                break
            nd = dist[v] + 1
            r = v // W
            c = v - r * W
            if r > 0:
                u = v - W
                if flat[u] == OPEN and dist[u] == -1:
                    dist[u] = nd
                    queue[tail] = u
                    tail += 1
            if r + 1 < H:
                u = v + W
                if flat[u] == OPEN and dist[u] == -1:
                    dist[u] = nd
                    queue[tail] = u
                    tail += 1
            if c > 0:
                u = v - 1
                if flat[u] == OPEN and dist[u] == -1:
                    dist[u] = nd
                    queue[tail] = u
                    tail += 1
            if c + 1 < W:
                u = v + 1
                if flat[u] == OPEN and dist[u] == -1:
                    dist[u] = nd
                    queue[tail] = u
                    tail += 1
        print(f'dist {d} seen {seen}')
        if d != -1:
            total += d
        qi += 1
    print(f'total {total}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
