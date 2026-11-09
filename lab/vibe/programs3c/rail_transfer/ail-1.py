import sys
import heapq


def main():
    data = sys.stdin.buffer.read().split()
    n = int(data[0])
    m = int(data[1])
    q = int(data[2])
    X = [int(data[3 + i]) for i in range(n)]
    p = 3 + n

    SH = 100000
    K = 1 << 22
    INF = 1 << 62

    us = [0] * m
    vs = [0] * m
    ls = [0] * m
    ts = [0] * m
    for i in range(m):
        us[i] = int(data[p])
        vs[i] = int(data[p + 1])
        ls[i] = int(data[p + 2])
        ts[i] = int(data[p + 3])
        p += 4

    # Ride-state ids: R(v, L) gets id >= n; A(v) = v for v < n.
    rid = {}
    owner = []
    cnt = n
    for i in range(m):
        u = us[i]
        v = vs[i]
        l = ls[i]
        for s in (u, v):
            key = s * SH + l
            if key not in rid:
                rid[key] = cnt
                cnt += 1
                owner.append(s)
    total = cnt

    # Directed ride edges in CSR form (src ride-state -> dst ride-state).
    E = 2 * m
    esrc = [0] * E
    edst = [0] * E
    ew = [0] * E
    for i in range(m):
        a = rid[us[i] * SH + ls[i]]
        b = rid[vs[i] * SH + ls[i]]
        w0 = ts[i] * K
        j = 2 * i
        esrc[j] = a
        edst[j] = b
        ew[j] = w0
        esrc[j + 1] = b
        edst[j + 1] = a
        ew[j + 1] = w0

    start = [0] * (total + 1)
    for a in esrc:
        start[a + 1] += 1
    for i in range(total):
        start[i + 1] += start[i]
    pos = start[:]
    dst = [0] * E
    w = [0] * E
    for e in range(E):
        a = esrc[e]
        k = pos[a]
        dst[k] = edst[e]
        w[k] = ew[e]
        pos[a] = k + 1

    # Ride-states belonging to each station (for boarding).
    blist = [[] for _ in range(n)]
    for r in range(n, total):
        blist[owner[r - n]].append(r)

    dist = [INF] * total
    out = []

    for _ in range(q):
        S = int(data[p])
        D = int(data[p + 1])
        p += 2
        if S == D:
            out.append("0 0")
            continue

        touched = []
        heap = []
        for r in blist[S]:
            dist[r] = 1
            touched.append(r)
            heap.append((1, r))
        heapq.heapify(heap)

        ans = None
        while heap:
            d, x = heapq.heappop(heap)
            if d > dist[x]:
                continue
            if x < n:
                if x == D:
                    ans = d
                    break
                xw = X[x] * K + 1
                for r in blist[x]:
                    nd = d + xw
                    if nd < dist[r]:
                        dist[r] = nd
                        touched.append(r)
                        heapq.heappush(heap, (nd, r))
            else:
                v = owner[x - n]
                if d < dist[v]:
                    dist[v] = d
                    touched.append(v)
                    heapq.heappush(heap, (d, v))
                for e in range(start[x], start[x + 1]):
                    nd = d + w[e]
                    y = dst[e]
                    if nd < dist[y]:
                        dist[y] = nd
                        touched.append(y)
                        heapq.heappush(heap, (nd, y))

        for t in touched:
            dist[t] = INF

        if ans is None:
            out.append("none")
        else:
            out.append(str(ans // K) + " " + str(ans % K))

    sys.stdout.write("\n".join(out) + ("\n" if out else ""))


main()
