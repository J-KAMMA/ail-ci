import sys
from heapq import heappush, heappop


def main():
    data = sys.stdin.buffer.read().split()
    B = int(data[0])
    S = int(data[1])
    cls = [0] * B
    rate = [0] * B
    pos = 2
    for b in range(B):
        cls[b] = int(data[pos])
        rate[b] = int(data[pos + 1])
        pos += 2
    ids = list(map(int, data[pos:pos + 6 * S:6]))
    arrs = list(map(int, data[pos + 1:pos + 6 * S:6]))
    sizes = list(map(int, data[pos + 2:pos + 6 * S:6]))
    cargos = list(map(int, data[pos + 3:pos + 6 * S:6]))
    prios = list(map(int, data[pos + 4:pos + 6 * S:6]))
    ops = list(map(int, data[pos + 5:pos + 6 * S:6]))
    del data

    keys = [(arrs[i] << 30) | ids[i] for i in range(S)]
    order = sorted(range(S), key=keys.__getitem__)
    del keys
    # re-index by (arrival, id)
    ids = [ids[i] for i in order]
    arrs = [arrs[i] for i in order]
    sizes = [sizes[i] for i in order]
    cargos = [cargos[i] for i in order]
    prios = [prios[i] for i in order]
    ops = [ops[i] for i in order]
    del order

    free = [[], [], [], []]
    for b in range(B):
        free[cls[b]].append(b)  # ascending already; sorted list is a valid heap
    wait = [None, [], [], []]
    busy = []
    lastop = [-1] * B
    nb = [0] * B
    ub = [0] * B
    start = [0] * S
    where = [0] * S
    SH = 22
    p = 0
    INF = 1 << 62
    makespan = 0
    total_wait = 0
    maxw = -1
    nwait = 0
    w1, w2, w3 = wait[1], wait[2], wait[3]
    f1, f2, f3 = free[1], free[2], free[3]
    while p < S or busy:
        ta = arrs[p] if p < S else INF
        td = (busy[0] >> 11) if busy else INF
        t = ta if ta < td else td
        while busy and (busy[0] >> 11) == t:
            b = heappop(busy) & 2047
            heappush(free[cls[b]], b)
        while p < S and arrs[p] == t:
            heappush(wait[sizes[p]], (prios[p] << SH) | p)
            p += 1
            nwait += 1
        if nwait:
            for c in (1, 2, 3):
                fc = free[c]
                while fc and nwait:
                    best = None
                    if w1:
                        best = w1[0]
                        bw = w1
                    if c >= 2 and w2 and (best is None or w2[0] < best):
                        best = w2[0]
                        bw = w2
                    if c >= 3 and w3 and (best is None or w3[0] < best):
                        best = w3[0]
                        bw = w3
                    if best is None:
                        break
                    heappop(bw)
                    nwait -= 1
                    b = heappop(fc)
                    i = best & 4194303
                    op = ops[i]
                    r = rate[b]
                    st = -(-cargos[i] // r) + (1 if lastop[b] == op else 4)
                    lastop[b] = op
                    end = t + st
                    nb[b] += 1
                    ub[b] += st
                    start[i] = t
                    where[i] = b
                    w = t - arrs[i]
                    total_wait += w
                    if w > maxw or (w == maxw and ids[i] < maxid):
                        maxw = w
                        maxid = ids[i]
                    if end > makespan:
                        makespan = end
                    heappush(busy, (end << 11) | b)
    out = ["ships %d" % S, "makespan %d" % makespan]
    if S == 0:
        out.append("wait total 0 max 0 ship -1")
    else:
        out.append("wait total %d max %d ship %d" % (total_wait, maxw, maxid))
    for b in range(B):
        out.append("berth %d ships %d busy %d" % (b, nb[b], ub[b]))
    g = 0
    M = 1000000007
    for i in sorted(range(S), key=ids.__getitem__):
        g = (g * 1000003 + start[i] * 31 + where[i]) % M
    out.append("digest %d" % g)
    sys.stdout.write("\n".join(out) + "\n")


main()
