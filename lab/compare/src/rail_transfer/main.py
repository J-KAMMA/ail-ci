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
    qs = []
    for i in range(Q):
        s = data[p]; d = data[p + 1]; p += 2
        qs.append((s, d))
    V = nid
    INF = 1 << 200
    dt = [INF] * (2 * V)
    done = [0] * (2 * V)
    out = []
    for s, d in qs:
        if s == d:
            out.append("0 0")
            continue
        t0 = []
        t1 = []
        heap0 = []
        heap1 = []
        best = INF
        # forward seeds: station S at (0, 0), its line nodes at (0, 1)
        if dt[s] == INF:
            t0.append(s)
        if 0 < dt[s]:
            dt[s] = 0
            heappush(heap0, s)
            if dt[V + s] != INF:
                z = dt[V + s]
                if z < best: best = z
        sl = st_lines[s]
        if sl is not None:
            for a in sl:
                if dt[a] == INF:
                    t0.append(a)
                if 1 < dt[a]:
                    dt[a] = 1
                    heappush(heap0, (1 << NB) | a)
                    if dt[V + a] != INF:
                        z = 1 + dt[V + a]
                        if z < best: best = z
        # backward seeds: station D at (0, 0), its line nodes at (0, 0)
        if dt[V + d] == INF:
            t1.append(d)
        if 0 < dt[V + d]:
            dt[V + d] = 0
            heappush(heap1, d)
            if dt[d] != INF:
                z = dt[d]
                if z < best: best = z
        sl = st_lines[d]
        if sl is not None:
            for a in sl:
                if dt[V + a] == INF:
                    t1.append(a)
                if 0 < dt[V + a]:
                    dt[V + a] = 0
                    heappush(heap1, a)
                    if dt[a] != INF:
                        z = dt[a]
                        if z < best: best = z
        while heap0 and heap1:
            if best != INF and (heap0[0] >> NB) + (heap1[0] >> NB) >= best:
                break
            if len(heap0) <= len(heap1):
                it = heappop(heap0)
                u = it & NMASK
                k = it >> NB
                idx = u
            else:
                it = heappop(heap1)
                u = it & NMASK
                k = it >> NB
                idx = V + u
            if done[idx] or k != dt[idx]:
                continue
            done[idx] = 1
            if u < N:
                sl = st_lines[u]
                if sl is not None:
                    if idx == u:
                        base = k + (X[u] << SH) + 1
                        for a in sl:
                            if not done[a] and base < dt[a]:
                                if dt[a] == INF: t0.append(a)
                                dt[a] = base
                                heappush(heap0, (base << NB) | a)
                                if dt[V + a] != INF:
                                    z = base + dt[V + a]
                                    if z < best: best = z
                    else:
                        for a in sl:
                            if not done[V + a] and k < dt[V + a]:
                                if dt[V + a] == INF: t1.append(a)
                                dt[V + a] = k
                                heappush(heap1, (k << NB) | a)
                                if dt[a] != INF:
                                    z = k + dt[a]
                                    if z < best: best = z
            else:
                hub = node_station[u]
                if idx == u:
                    if not done[hub] and k < dt[hub]:
                        if dt[hub] == INF: t0.append(hub)
                        dt[hub] = k
                        heappush(heap0, (k << NB) | hub)
                        if dt[V + hub] != INF:
                            z = k + dt[V + hub]
                            if z < best: best = z
                else:
                    base = k + (X[hub] << SH) + 1
                    if not done[V + hub] and base < dt[V + hub]:
                        if dt[V + hub] == INF: t1.append(hub)
                        dt[V + hub] = base
                        heappush(heap1, (base << NB) | hub)
                        if dt[hub] != INF:
                            z = base + dt[hub]
                            if z < best: best = z
                for e in adj[u]:
                    nk = k + (e >> NB)
                    v = e & NMASK
                    if idx == u:
                        if not done[v] and nk < dt[v]:
                            if dt[v] == INF: t0.append(v)
                            dt[v] = nk
                            heappush(heap0, (nk << NB) | v)
                            if dt[V + v] != INF:
                                z = nk + dt[V + v]
                                if z < best: best = z
                    else:
                        if not done[V + v] and nk < dt[V + v]:
                            if dt[V + v] == INF: t1.append(v)
                            dt[V + v] = nk
                            heappush(heap1, (nk << NB) | v)
                            if dt[v] != INF:
                                z = nk + dt[v]
                                if z < best: best = z
        for u in t0:
            dt[u] = INF
            done[u] = 0
        for u in t1:
            dt[V + u] = INF
            done[V + u] = 0
        if best == INF:
            out.append("none")
        else:
            out.append("%d %d" % (best >> SH, best & MASK))
    sys.stdout.write("\n".join(out) + ("\n" if out else ""))


main()
