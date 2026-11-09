import sys
import heapq


def main():
    data = sys.stdin.buffer.read().split()
    n = int(data[0])
    m = int(data[1])
    q = int(data[2])
    p = 3
    X = [int(x) for x in data[p:p + n]]
    p += n

    SH = 100000
    BASE = 10 ** 9      # riding-state keys are BASE + v*SH + L (always >= BASE)
    B = 1 << 22         # boardings are stored in the low bits of the cost key
    INF = float("inf")

    adj = {}
    lines_at = [[] for _ in range(n)]

    for _ in range(m):
        U = int(data[p])
        V = int(data[p + 1])
        L = int(data[p + 2])
        T = int(data[p + 3])
        p += 4
        ku = BASE + U * SH + L
        kv = BASE + V * SH + L
        lst = adj.get(ku)
        if lst is None:
            adj[ku] = [(V, T)]
            lines_at[U].append(L)
        else:
            lst.append((V, T))
        lst = adj.get(kv)
        if lst is None:
            adj[kv] = [(U, T)]
            lines_at[V].append(L)
        else:
            lst.append((U, T))

    out = []
    for _ in range(q):
        S = int(data[p])
        D = int(data[p + 1])
        p += 2
        if S == D:
            out.append("0 0")
            continue

        dist = {}
        heap = []

        # First ride from S: no transfer cost.
        for L in lines_at[S]:
            for (u, T) in adj[BASE + S * SH + L]:
                nk = BASE + u * SH + L
                nc = T * B + 1
                if nc < dist.get(nk, INF):
                    dist[nk] = nc
                    heapq.heappush(heap, (nc, nk))

        ans = None
        while heap:
            c, k = heapq.heappop(heap)
            if dist.get(k, INF) != c:
                continue
            if k < BASE:
                # Idle at station k (alighted, may board with transfer cost).
                v = k
                if v == D:
                    ans = c
                    break
                xb = X[v] * B + 1
                for L in lines_at[v]:
                    for (u, T) in adj[BASE + v * SH + L]:
                        nk = BASE + u * SH + L
                        nc = c + xb + T * B
                        if nc < dist.get(nk, INF):
                            dist[nk] = nc
                            heapq.heappush(heap, (nc, nk))
            else:
                r = k - BASE
                v = r // SH
                L = r - v * SH
                # Alight at v (free, no boarding change).
                if c < dist.get(v, INF):
                    dist[v] = c
                    heapq.heappush(heap, (c, v))
                # Continue riding line L.
                for (u, T) in adj[k]:
                    nk = BASE + u * SH + L
                    nc = c + T * B
                    if nc < dist.get(nk, INF):
                        dist[nk] = nc
                        heapq.heappush(heap, (nc, nk))

        if ans is None:
            out.append("none")
        else:
            out.append("%d %d" % (ans // B, ans % B))

    sys.stdout.write("\n".join(out) + ("\n" if out else ""))


if __name__ == "__main__":
    main()
