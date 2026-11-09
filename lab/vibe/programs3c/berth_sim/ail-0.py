import sys
import heapq


def main():
    data = sys.stdin.buffer.read().split()
    B = int(data[0])
    S = int(data[1])
    pos = 2
    cls = [0] * B
    rate = [0] * B
    for b in range(B):
        cls[b] = int(data[pos])
        rate[b] = int(data[pos + 1])
        pos += 2

    ships = []
    for _ in range(S):
        sid = int(data[pos])
        arr = int(data[pos + 1])
        size = int(data[pos + 2])
        cargo = int(data[pos + 3])
        pr = int(data[pos + 4])
        op = int(data[pos + 5])
        pos += 6
        ships.append((arr, sid, size, cargo, op, pr))
    del data
    ships.sort()

    # free berths per class, as heaps of berth numbers
    free = [[], [], [], []]
    for b in range(B):
        free[cls[b]].append(b)  # already ascending, a valid heap

    # waiting ships per size, as heaps keyed by (priority, arrival, id)
    wq = [[], [], [], []]

    last_op = [-1] * B
    cnt = [0] * B
    busy = [0] * B
    D = []  # departures encoded as end * 2048 + berth
    res = []
    W = 0
    X = -1
    XI = -1
    M = 0
    i = 0
    served = 0

    while served < S:
        t = None
        if i < S:
            t = ships[i][0]
        if D:
            dt = D[0] >> 11
            if t is None or dt < t:
                t = dt
        if t is None:
            break

        # 1. departures at t
        while D and (D[0] >> 11) == t:
            v = heapq.heappop(D)
            b = v & 2047
            heapq.heappush(free[cls[b]], b)

        # 2. arrivals at t
        while i < S and ships[i][0] == t:
            a = ships[i]
            heapq.heappush(wq[a[2]], (a[5], a[0], a[1], a[3], a[4]))
            i += 1

        # 3. assignment, classes ascending, berths ascending within class
        for c in (1, 2, 3):
            fc = free[c]
            while fc:
                best = None
                bs = 0
                for z in range(1, c + 1):
                    q = wq[z]
                    if q and (best is None or q[0] < best):
                        best = q[0]
                        bs = z
                if best is None:
                    break
                b = heapq.heappop(fc)
                heapq.heappop(wq[bs])
                pr, arr, sid, cargo, op = best
                setup = 1 if last_op[b] == op else 4
                last_op[b] = op
                rt = rate[b]
                svc = (cargo + rt - 1) // rt + setup
                end = t + svc
                heapq.heappush(D, (end << 11) | b)
                cnt[b] += 1
                busy[b] += svc
                w = t - arr
                W += w
                if w > X or (w == X and sid < XI):
                    X = w
                    XI = sid
                if end > M:
                    M = end
                res.append((sid, t, b))
                served += 1

    if S == 0:
        X = 0
        XI = -1

    out = []
    out.append("ships %d\n" % S)
    out.append("makespan %d\n" % M)
    out.append("wait total %d max %d ship %d\n" % (W, X, XI))
    for b in range(B):
        out.append("berth %d ships %d busy %d\n" % (b, cnt[b], busy[b]))

    res.sort()
    g = 0
    MOD = 1000000007
    for sid, st, b in res:
        g = (g * 1000003 + st * 31 + b) % MOD
    out.append("digest %d\n" % g)
    sys.stdout.write("".join(out))


main()
