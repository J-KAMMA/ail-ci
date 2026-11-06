import sys
import heapq
from array import array


def main():
    data = sys.stdin.buffer
    readline = data.readline

    first = readline().split()
    if not first:
        return
    N = int(first[0]); M = int(first[1]); Q = int(first[2])

    if Q == 0:
        return

    X = []
    while len(X) < N:
        X.extend(map(int, readline().split()))

    state_id = {}
    head = array('i')
    to = array('i')
    wt = array('i')
    nxt = array('i')
    station_of = array('i')
    station_head = array('i', [-1]) * N
    station_next = array('i')

    head_append = head.append
    to_append = to.append
    wt_append = wt.append
    nxt_append = nxt.append
    station_of_append = station_of.append
    station_next_append = station_next.append

    for _ in range(M):
        parts = readline().split()
        u = int(parts[0]); v = int(parts[1]); L = int(parts[2]); T = int(parts[3])

        key = u * 100000 + L
        sid = state_id.get(key)
        if sid is None:
            sid = len(head)
            state_id[key] = sid
            head_append(-1)
            station_of_append(u)
            station_next_append(station_head[u])
            station_head[u] = sid

        key = v * 100000 + L
        tid = state_id.get(key)
        if tid is None:
            tid = len(head)
            state_id[key] = tid
            head_append(-1)
            station_of_append(v)
            station_next_append(station_head[v])
            station_head[v] = tid

        to_append(tid); wt_append(T); nxt_append(head[sid]); head[sid] = len(to) - 1
        to_append(sid); wt_append(T); nxt_append(head[tid]); head[tid] = len(to) - 1

    del state_id

    queries = []
    src_set = set()
    dst_set = set()
    for _ in range(Q):
        parts = readline().split()
        s = int(parts[0]); d = int(parts[1])
        queries.append((s, d))
        src_set.add(s)
        dst_set.add(d)

    use_dst = len(dst_set) < len(src_set)

    sc = len(head)

    vtime = array('q', [0]) * sc
    vboard = array('i', [0]) * sc
    vver = array('i', [0]) * sc
    vdone = array('i', [0]) * sc

    Btime = array('q', [0]) * N
    Bboard = array('i', [0]) * N
    Bver = array('i', [0]) * N
    Bdone = array('i', [0]) * N

    NBITS = 22
    NMASK = (1 << NBITS) - 1
    BBITS = 23
    BMASK = (1 << BBITS) - 1
    NODE_OFF = sc

    answers = [None] * Q
    groups = {}
    for idx, (s, d) in enumerate(queries):
        if s == d:
            answers[idx] = "0 0"
            continue
        if use_dst:
            key = d; target = s
        else:
            key = s; target = d
        g = groups.get(key)
        if g is None:
            groups[key] = [(idx, target)]
        else:
            g.append((idx, target))

    heappush = heapq.heappush
    heappop = heapq.heappop

    ver = 0
    for s, targets in groups.items():
        ver += 1
        dest_map = {}
        for idx, d in targets:
            g = dest_map.get(d)
            if g is None:
                dest_map[d] = [idx]
            else:
                g.append(idx)
        remaining = len(dest_map)
        heap = []

        ls = station_head[s]
        while ls != -1:
            vver[ls] = ver
            vtime[ls] = 0
            vboard[ls] = 1
            heappush(heap, (1 << NBITS) | ls)
            ls = station_next[ls]

        while heap and remaining:
            key = heappop(heap)
            node = key & NMASK
            rest = key >> NBITS
            b = rest & BMASK
            t = rest >> BBITS

            if node < sc:
                if vdone[node] == ver:
                    continue
                vdone[node] = ver
                u = station_of[node]

                if Bver[u] != ver or (t, b) < (Btime[u], Bboard[u]):
                    Bver[u] = ver
                    Btime[u] = t
                    Bboard[u] = b
                    heappush(heap, (((t << BBITS) | b) << NBITS) | (NODE_OFF + u))

                e = head[node]
                while e != -1:
                    ns = to[e]
                    nt = t + wt[e]
                    if vver[ns] != ver or (nt, b) < (vtime[ns], vboard[ns]):
                        vver[ns] = ver
                        vtime[ns] = nt
                        vboard[ns] = b
                        heappush(heap, (((nt << BBITS) | b) << NBITS) | ns)
                    e = nxt[e]
            else:
                u = node - NODE_OFF
                if Bdone[u] == ver:
                    continue
                Bdone[u] = ver

                ids = dest_map.get(u)
                if ids is not None:
                    val = str(t) + " " + str(b)
                    for idx in ids:
                        answers[idx] = val
                    del dest_map[u]
                    remaining -= 1
                    if remaining == 0:
                        break

                xu = X[u]
                nb = b + 1
                nt = t + xu
                ls = station_head[u]
                while ls != -1:
                    if vver[ls] != ver or (nt, nb) < (vtime[ls], vboard[ls]):
                        vver[ls] = ver
                        vtime[ls] = nt
                        vboard[ls] = nb
                        heappush(heap, (((nt << BBITS) | nb) << NBITS) | ls)
                    ls = station_next[ls]

        for d, ids in dest_map.items():
            for idx in ids:
                answers[idx] = "none"

    sys.stdout.write("\n".join(answers))
    if answers:
        sys.stdout.write("\n")


if __name__ == "__main__":
    main()
