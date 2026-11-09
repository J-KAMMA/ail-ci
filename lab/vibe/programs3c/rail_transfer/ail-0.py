import sys
import heapq


def main():
    data = sys.stdin.buffer.read().split()
    N = int(data[0])
    M = int(data[1])
    Q = int(data[2])
    pos = 3
    X = [int(x) for x in data[pos:pos + N]]
    pos += N

    # R nodes: (station, line) pairs that have at least one non-loop segment.
    # Graph node ids: 0..N-1 = "at station, free to alight" (A nodes),
    # N + r = "riding line of R-node r" (R nodes).
    key_map = {}
    st_of = []
    radj = []
    stR = [[] for _ in range(N)]

    for _ in range(M):
        u = int(data[pos])
        v = int(data[pos + 1])
        l = int(data[pos + 2])
        t = int(data[pos + 3])
        pos += 4
        if u == v:
            continue
        k1 = u * 100000 + l
        a = key_map.get(k1)
        if a is None:
            a = len(st_of)
            key_map[k1] = a
            st_of.append(u)
            radj.append([])
            stR[u].append(a)
        k2 = v * 100000 + l
        b = key_map.get(k2)
        if b is None:
            b = len(st_of)
            key_map[k2] = b
            st_of.append(v)
            radj.append([])
            stR[v].append(b)
        radj[a].append((b, t))
        radj[b].append((a, t))

    out = []
    for _ in range(Q):
        S = int(data[pos])
        D = int(data[pos + 1])
        pos += 2
        if S == D:
            out.append("0 0")
            continue

        dist = {}
        done = set()
        heap = []
        for a in stR[S]:
            node = N + a
            dist[node] = (0, 1)
            heap.append((0, 1, node))
        heapq.heapify(heap)

        result = None
        while heap:
            t, b, x = heapq.heappop(heap)
            if x in done:
                continue
            cur = dist.get(x)
            if cur is not None and cur != (t, b):
                continue
            done.add(x)
            if x == D:
                result = (t, b)
                break
            if x < N:
                # At station x: board any line here (transfer charge, one more ride).
                tx = X[x]
                for a in stR[x]:
                    y = N + a
                    if y in done:
                        continue
                    nt = t + tx
                    nb = b + 1
                    c = dist.get(y)
                    if c is None or (nt, nb) < c:
                        dist[y] = (nt, nb)
                        heapq.heappush(heap, (nt, nb, y))
            else:
                r = x - N
                # Alight at the station.
                s = st_of[r]
                if s not in done:
                    c = dist.get(s)
                    if c is None or (t, b) < c:
                        dist[s] = (t, b)
                        heapq.heappush(heap, (t, b, s))
                # Ride along the same line.
                for (nb_r, tt) in radj[r]:
                    y = N + nb_r
                    if y in done:
                        continue
                    nt = t + tt
                    c = dist.get(y)
                    if c is None or (nt, b) < c:
                        dist[y] = (nt, b)
                        heapq.heappush(heap, (nt, b, y))

        if result is None:
            out.append("none")
        else:
            out.append("%d %d" % (result[0], result[1]))

    if out:
        sys.stdout.write("\n".join(out) + "\n")
    sys.exit(0)


main()
