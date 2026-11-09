import sys
import heapq


def main():
    readline = sys.stdin.readline
    first = readline()
    if not first:
        return

    parts = first.split()
    if not parts:
        return

    N = int(parts[0])
    M = int(parts[1])
    Q = int(parts[2])

    if Q == 0:
        return

    X = []
    while len(X) < N:
        X.extend(map(int, readline().split()))

    SHIFT = 20
    MASK = (1 << SHIFT) - 1

    line_maps = {}
    station_incs = [[] for _ in range(N)]
    adj = []
    inc_station = []

    for _ in range(M):
        u, v, L, T = map(int, readline().split())

        d = line_maps.get(L)
        if d is None:
            d = {}
            line_maps[L] = d

        iu = d.get(u)
        if iu is None:
            iu = N + len(adj)
            d[u] = iu
            adj.append([])
            inc_station.append(u)
            station_incs[u].append(iu)

        iv = d.get(v)
        if iv is None:
            iv = N + len(adj)
            d[v] = iv
            adj.append([])
            inc_station.append(v)
            station_incs[v].append(iv)

        if iu != iv:
            adj[iu - N].append((iv << SHIFT) | T)
            adj[iv - N].append((iu << SHIFT) | T)

    line_maps = None

    queries = []
    for _ in range(Q):
        S, D = map(int, readline().split())
        queries.append((S, D))

    ans = [None] * Q
    groups = {}

    for idx in range(Q):
        S, D = queries[idx]
        if S == D:
            ans[idx] = (0, 0)
        else:
            g = groups.get(S)
            if g is None:
                g = {}
                groups[S] = g
            lst = g.get(D)
            if lst is None:
                lst = []
                g[D] = lst
            lst.append(idx)

    queries = None

    total = N + len(adj)
    stamp = [0] * total
    dist = [0] * total
    boards = [0] * total

    qid = 0

    for S in list(groups):
        tmap = groups[S]
        qid += 1

        heap = []
        for g in station_incs[S]:
            stamp[g] = qid
            dist[g] = 0
            boards[g] = 1
            heapq.heappush(heap, (0, 1, g))

        remaining = len(tmap)

        while heap and remaining > 0:
            t, b, u = heapq.heappop(heap)

            if stamp[u] != qid or t != dist[u] or b != boards[u]:
                continue

            if u < N:
                ids = tmap.get(u)
                if ids is not None:
                    for idx in ids:
                        ans[idx] = (t, b)
                    del tmap[u]
                    remaining -= 1

                w = X[u]
                nb = b + 1

                for g in station_incs[u]:
                    nt = t + w
                    if stamp[g] != qid:
                        stamp[g] = qid
                        dist[g] = nt
                        boards[g] = nb
                        heapq.heappush(heap, (nt, nb, g))
                    elif nt < dist[g] or (nt == dist[g] and nb < boards[g]):
                        dist[g] = nt
                        boards[g] = nb
                        heapq.heappush(heap, (nt, nb, g))
            else:
                j = u - N

                for code in adj[j]:
                    g = code >> SHIFT
                    nt = t + (code & MASK)

                    if stamp[g] != qid:
                        stamp[g] = qid
                        dist[g] = nt
                        boards[g] = b
                        heapq.heappush(heap, (nt, b, g))
                    elif nt < dist[g] or (nt == dist[g] and b < boards[g]):
                        dist[g] = nt
                        boards[g] = b
                        heapq.heappush(heap, (nt, b, g))

                v = inc_station[j]

                if stamp[v] != qid:
                    stamp[v] = qid
                    dist[v] = t
                    boards[v] = b
                    heapq.heappush(heap, (t, b, v))
                elif t < dist[v] or (t == dist[v] and b < boards[v]):
                    dist[v] = t
                    boards[v] = b
                    heapq.heappush(heap, (t, b, v))

    out = []
    for i in range(Q):
        a = ans[i]
        if a is None:
            out.append("none")
        else:
            out.append(str(a[0]) + " " + str(a[1]))

    sys.stdout.write("\n".join(out))
    sys.stdout.write("\n")


if __name__ == "__main__":
    main()
