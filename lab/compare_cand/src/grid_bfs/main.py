import sys

WALL = '#'
OPEN = '.'


def number(tok):
    n = len(tok)
    if n == 0:
        return -1
    v = 0
    i = 0
    while i < n:
        c = tok[i]
        if c < '0' or c > '9':
            return -1
        v = v * 10 + (ord(c) - 48)
        if v > 100000000:
            return -1
        i += 1
    return v


def main():
    data = sys.stdin.read()
    if data == '':
        return 2
    lines = data.split('\n')
    nl = len(lines)
    if nl > 0 and lines[nl - 1] == '':
        nl -= 1
    if nl < 1:
        return 2
    head = lines[0].split(' ')
    if len(head) != 3:
        return 2
    H = number(head[0])
    W = number(head[1])
    Q = number(head[2])
    if H < 1 or H > 2000 or W < 1 or W > 2000 or Q < 0 or Q > 20:
        return 2
    if nl != 1 + H + Q:
        return 2
    rows = []
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
        rows.append(row)
        i += 1
    queries = []
    i = 1 + H
    k = 0
    while k < Q:
        parts = lines[i].split(' ')
        if len(parts) != 4:
            return 2
        r1 = number(parts[0])
        c1 = number(parts[1])
        r2 = number(parts[2])
        c2 = number(parts[3])
        if (r1 < 0 or r1 >= H or c1 < 0 or c1 >= W
                or r2 < 0 or r2 >= H or c2 < 0 or c2 >= W):
            return 2
        queries.append((r1, c1, r2, c2))
        i += 1
        k += 1
    flat = ''.join(rows)
    n = H * W
    out = []
    total = 0
    qi = 0
    nq = len(queries)
    while qi < nq:
        r1, c1, r2, c2 = queries[qi]
        s = r1 * W + c1
        t = r2 * W + c2
        if flat[s] == WALL or flat[t] == WALL:
            out.append('dist -1 seen 0')
            qi += 1
            continue
        dist = [-1] * n
        queue = [0] * n
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
        out.append('dist %d seen %d' % (d, seen))
        if d != -1:
            total += d
        qi += 1
    out.append('total %d' % total)
    sys.stdout.write('\n'.join(out) + '\n')
    return 0


sys.exit(main())
