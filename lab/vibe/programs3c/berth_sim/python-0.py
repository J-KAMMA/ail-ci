import sys
import heapq
from array import array


def main():
    inp = sys.stdin.buffer
    heappush = heapq.heappush
    heappop = heapq.heappop

    first = inp.readline().split()
    B = int(first[0])
    S = int(first[1])

    cls = [0] * B
    rate = [1] * B
    for b in range(B):
        parts = inp.readline().split()
        cls[b] = int(parts[0])
        rate[b] = int(parts[1])

    ids = array('q', [0]) * S
    arrs = array('q', [0]) * S
    sizes = array('q', [0]) * S
    cargos = array('q', [0]) * S
    prios = array('q', [0]) * S
    ops = array('q', [0]) * S

    for i in range(S):
        p = inp.readline().split()
        ids[i] = int(p[0])
        arrs[i] = int(p[1])
        sizes[i] = int(p[2])
        cargos[i] = int(p[3])
        prios[i] = int(p[4])
        ops[i] = int(p[5])

    MASK = (1 << 22) - 1
    MOD = 1000000007

    order = sorted((arrs[i] << 22) | i for i in range(S))

    free = [None, [], [], []]
    for b in range(B):
        free[cls[b]].append(b)
    for c in (1, 2, 3):
        heapq.heapify(free[c])

    sheap = [[], [], [], []]
    last_op = [-1] * B
    cnt = [0] * B
    busy = [0] * B
    start = array('q', [0]) * S
    berth_of = array('q', [0]) * S
    dh = []
    makespan = 0
    ap = 0

    while ap < S or dh:
        if ap < S:
            t = order[ap] >> 22
            if dh and (dh[0] >> 11) < t:
                t = dh[0] >> 11
        else:
            t = dh[0] >> 11

        while dh and (dh[0] >> 11) == t:
            b = heappop(dh) & 2047
            heappush(free[cls[b]], b)

        while ap < S and (order[ap] >> 22) == t:
            i = order[ap] & MASK
            ap += 1
            key = (((((prios[i] << 30) | arrs[i]) << 30) | ids[i]) << 22) | i
            heappush(sheap[sizes[i]], key)

        for c in (1, 2, 3):
            fr = free[c]
            while fr:
                best = None
                bz = -1
                for z in range(1, c + 1):
                    h = sheap[z]
                    if h and (best is None or h[0] < best):
                        best = h[0]
                        bz = z
                if best is None:
                    break
                heappop(sheap[bz])
                i = best & MASK
                b = heappop(fr)
                rt = rate[b]
                svc = (cargos[i] + rt - 1) // rt + (1 if last_op[b] == ops[i] else 4)
                last_op[b] = ops[i]
                start[i] = t
                berth_of[i] = b
                end = t + svc
                cnt[b] += 1
                busy[b] += svc
                heappush(dh, (end << 11) | b)
                if end > makespan:
                    makespan = end

    W = 0
    mx = -1
    mxid = -1
    for i in range(S):
        w = start[i] - arrs[i]
        W += w
        if w > mx or (w == mx and ids[i] < mxid):
            mx = w
            mxid = ids[i]
    if S == 0:
        mx = 0
        mxid = -1

    keys = sorted((ids[i] << 22) | i for i in range(S))
    g = 0
    for k in keys:
        i = k & MASK
        g = (g * 1000003 + start[i] * 31 + berth_of[i]) % MOD

    out = []
    out.append("ships %d\n" % S)
    out.append("makespan %d\n" % makespan)
    out.append("wait total %d max %d ship %d\n" % (W, mx, mxid))
    for b in range(B):
        out.append("berth %d ships %d busy %d\n" % (b, cnt[b], busy[b]))
    out.append("digest %d\n" % g)
    sys.stdout.write("".join(out))


if __name__ == "__main__":
    main()
