import sys
import heapq


def main():
    data = sys.stdin.buffer.read().split()
    n = int(data[0])
    m = int(data[1])
    q = int(data[2])
    X = [int(x) for x in data[3:3 + n]]
    pos = 3 + n

    SH = 23                 # boardings field width in the combined cost
    K = 1 << SH
    BMASK = K - 1
    NMASK = (1 << 22) - 1   # node id field (node ids < 2^22)

    # Nodes: 0..n-1 are P(v) = "at station v, free to board a ride".
    # Nodes >= n are A(v,L) = "currently riding line L at station v".
    adj = [[] for _ in range(n)]
    station_of = list(range(n))
    ida = {}
    nxt = n

    for _ in range(m):
        u = int(data[pos])
        v = int(data[pos + 1])
        l = int(data[pos + 2])
        t = int(data[pos + 3])
        pos += 4

        ku = u * 100000 + l
        iu = ida.get(ku)
        if iu is None:
            iu = nxt
            ida[ku] = iu
            nxt += 1
            adj.append([])
            station_of.append(u)

        kv = v * 100000 + l
        iv = ida.get(kv)
        if iv is None:
            iv = nxt
            ida[kv] = iv
            nxt += 1
            adj.append([])
            station_of.append(v)

        tc = t << SH
        tb = tc | 1  # boarding a new ride adds one boarding
        # riding line L along the segment (cost time only)
        adj[iu].append((tc << 22) | iv)
        adj[iv].append((tc << 22) | iu)
        # boarding at P(u) / P(v)
        adj[u].append((tb << 22) | iv)
        adj[v].append((tb << 22) | iu)

    # transfer: from A(s,L) to P(s), paying X_s time
    for a in range(n, nxt):
        s = station_of[a]
        adj[a].append(((X[s] << SH) << 22) | s)

    INF = 1 << 200
    heappop = heapq.heappop
    heappush = heapq.heappush

    res = [""] * q
    by_src = {}
    for i in range(q):
        s = int(data[pos])
        d = int(data[pos + 1])
        pos += 2
        if s == d:
            res[i] = "0 0\n"
        else:
            by_src.setdefault(s, {}).setdefault(d, []).append(i)

    for s, tgts in by_src.items():
        remaining = len(tgts)
        found = {}
        dist = {s: 0}
        heap = [(0, s)]
        while heap and remaining > 0:
            d, x = heappop(heap)
            if d != dist[x]:
                continue
            if x >= n:
                st = station_of[x]
                if st in tgts and st not in found:
                    found[st] = d
                    remaining -= 1
                    if remaining == 0:
                        break
            for e in adj[x]:
                y = e & NMASK
                nd = d + (e >> 22)
                if nd < dist.get(y, INF):
                    dist[y] = nd
                    heappush(heap, (nd, y))

        for dst, idxs in tgts.items():
            if dst in found:
                dd = found[dst]
                line = "%d %d\n" % (dd >> SH, dd & BMASK)
            else:
                line = "none\n"
            for i in idxs:
                res[i] = line

    sys.stdout.write("".join(res))


if __name__ == "__main__":
    main()
