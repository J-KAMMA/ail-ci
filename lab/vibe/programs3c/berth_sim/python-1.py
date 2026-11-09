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

    ids = [0] * S
    arr = [0] * S
    size = [0] * S
    cargo = [0] * S
    prio = [0] * S
    opr = [0] * S
    for i in range(S):
        ids[i] = int(data[pos])
        arr[i] = int(data[pos + 1])
        size[i] = int(data[pos + 2])
        cargo[i] = int(data[pos + 3])
        prio[i] = int(data[pos + 4])
        opr[i] = int(data[pos + 5])
        pos += 6

    border = sorted(range(B), key=lambda b: (cls[b], b))
    rrank = [0] * B
    for r, b in enumerate(border):
        rrank[b] = r

    order = sorted(range(S), key=arr.__getitem__)

    heappush = heapq.heappush
    heappop = heapq.heappop

    free = list(range(B))  # ranks; sorted list is a valid heap
    heaps = [[], [], [], []]
    dep = []
    last_op = [-1] * B
    cnt = [0] * B
    busy = [0] * B
    start = [0] * S
    sberth = [0] * S
    W = 0
    X = -1
    I = -1
    makespan = 0
    waiting = 0
    INF = float("inf")
    p = 0

    while p < S or dep:
        ta = arr[order[p]] if p < S else INF
        td = dep[0][0] if dep else INF
        t = ta if ta < td else td

        while dep and dep[0][0] == t:
            _, b = heappop(dep)
            heappush(free, rrank[b])

        while p < S and arr[order[p]] == t:
            i = order[p]
            heappush(heaps[size[i]], (prio[i], t, ids[i], i))
            waiting += 1
            p += 1

        if waiting and free:
            left = []
            while free and waiting:
                r = heappop(free)
                b = border[r]
                c = cls[b]
                best = None
                bz = 0
                for z in range(1, c + 1):
                    h = heaps[z]
                    if h and (best is None or h[0] < best):
                        best = h[0]
                        bz = z
                if best is None:
                    left.append(r)
                    continue
                _, _, sid, i = heappop(heaps[bz])
                waiting -= 1
                op = opr[i]
                setup = 1 if last_op[b] == op else 4
                last_op[b] = op
                svc = -(-cargo[i] // rate[b]) + setup
                w = t - arr[i]
                W += w
                if w > X or (w == X and sid < I):
                    X = w
                    I = sid
                start[i] = t
                sberth[i] = b
                busy[b] += svc
                cnt[b] += 1
                end = t + svc
                if end > makespan:
                    makespan = end
                heappush(dep, (end, b))
            for r in left:
                heappush(free, r)

    MOD = 1000000007
    order_id = sorted(range(S), key=ids.__getitem__)
    g = 0
    for i in order_id:
        g = (g * 1000003 + start[i] * 31 + sberth[i]) % MOD

    out = [f"ships {S}", f"makespan {makespan}"]
    if S:
        out.append(f"wait total {W} max {X} ship {I}")
    else:
        out.append("wait total 0 max 0 ship -1")
    for b in range(B):
        out.append(f"berth {b} ships {cnt[b]} busy {busy[b]}")
    out.append(f"digest {g}")
    sys.stdout.write("\n".join(out) + "\n")


main()
