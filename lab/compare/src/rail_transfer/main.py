import sys
from heapq import heappush, heappop


def main():
    data = list(map(int, sys.stdin.buffer.read().split()))
    N = int(data[0]); M = int(data[1]); Q = int(data[2])
    X = data[3:3 + N]
    p = 3 + N
    SH = 24
    MASK = (1 << SH) - 1
    NB = 22
    NMASK = (1 << NB) - 1
    ids = {}
    node_station = [0] * N  # index by node id; extended for line nodes
    st_lines = [None] * N
    adj = [None] * N  # adjacency for all nodes (station nodes unused)
    nid = N
    for i in range(M):
        u = data[p]; v = data[p + 1]; L = data[p + 2]; t = data[p + 3]
        p += 4
        ku = u * 100000 + L
        a = ids.get(ku)
        if a is None:
            a = nid; nid += 1
            ids[ku] = a
            node_station.append(u)
            adj.append([])
            if st_lines[u] is None:
                st_lines[u] = [a]
            else:
                st_lines[u].append(a)
        if u == v:
            continue
        kv = v * 100000 + L
        b = ids.get(kv)
        if b is None:
            b = nid; nid += 1
            ids[kv] = b
            node_station.append(v)
            adj.append([])
            if st_lines[v] is None:
                st_lines[v] = [b]
            else:
                st_lines[v].append(b)
        ts = t << SH
        adj[a].append((ts << NB) | b)
        adj[b].append((ts << NB) | a)
    del ids
    # group queries by source
    qs = []
    bysrc = {}
    for i in range(Q):
        s = data[p]; d = data[p + 1]; p += 2
        qs.append((s, d))
        if s != d:
            bysrc.setdefault(s, set()).add(d)
        res = {}
    INF = 1 << 200
    for s, dests in bysrc.items():
        sl = st_lines[s]
        if sl is None:
            for d in dests:
                res[(s, d)] = None
            continue
        dist = [INF] * nid
        remaining = len(dests)
        heap = []
        for a in sl:
            dist[a] = 1
            heap.append((1 << NB) | a)
        heap.sort()
        while heap and remaining:
            it = heappop(heap)
            u = it & NMASK
            k = it >> NB
            if dist[u] != k:
                continue
            if u < N:
                if u in dests:
                    res[(s, u)] = k
                    remaining -= 1
                sl = st_lines[u]
                if sl is not None:
                    nk = k + (X[u] << SH) + 1
                    for a in sl:
                        if nk < dist[a]:
                            dist[a] = nk
                            heappush(heap, (nk << NB) | a)
            else:
                w = node_station[u]
                if k < dist[w]:
                    dist[w] = k
                    heappush(heap, (k << NB) | w)
                for e in adj[u]:
                    nk = k + (e >> NB)
                    w = e & NMASK
                    if nk < dist[w]:
                        dist[w] = nk
                        heappush(heap, (nk << NB) | w)
        for d in dests:
            if (s, d) not in res:
                res[(s, d)] = None
    out = []
    for s, d in qs:
        if s == d:
            out.append("0 0")
        else:
            k = res[(s, d)]
            if k is None:
                out.append("none")
            else:
                out.append("%d %d" % (k >> SH, k & MASK))
    sys.stdout.write("\n".join(out) + ("\n" if out else ""))


main()
