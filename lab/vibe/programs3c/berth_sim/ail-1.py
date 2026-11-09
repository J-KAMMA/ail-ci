import sys
from heapq import heappush, heappop


def main():
    data = sys.stdin.buffer.read().split()
    B = int(data[0])
    S = int(data[1])
    p = 2
    bcls = [0] * B
    brate = [1] * B
    for i in range(B):
        bcls[i] = int(data[p])
        brate[i] = int(data[p + 1])
        p += 2

    if S == 0:
        out = ["ships 0", "makespan 0", "wait total 0 max 0 ship -1"]
        for b in range(B):
            out.append("berth %d ships 0 busy 0" % b)
        out.append("digest 0")
        sys.stdout.write("\n".join(out) + "\n")
        return

    vals = list(map(int, data[p:p + 6 * S]))
    ID0 = vals[0::6]
    AR0 = vals[1::6]
    SZ0 = vals[2::6]
    CG0 = vals[3::6]
    PR0 = vals[4::6]
    OP0 = vals[5::6]
    del vals

    # rank ships by (PRIORITY, ARRIVAL, ID); rank is the "best" order
    order = sorted(range(S), key=lambda i: (PR0[i], AR0[i], ID0[i]))
    ID = [ID0[o] for o in order]
    ARR = [AR0[o] for o in order]
    SZ = [SZ0[o] for o in order]
    CG = [CG0[o] for o in order]
    OP = [OP0[o] for o in order]
    del ID0, AR0, SZ0, CG0, PR0, OP0, order

    arr_order = sorted(range(S), key=lambda r: ARR[r])
    AS = [ARR[r] for r in arr_order]

    H = [[], [], [], []]
    FB = [[], [], [], []]
    for b in range(B):
        FB[bcls[b]].append(b)  # ascending indices form a valid heap

    last = [-1] * B
    busy = [0] * B
    cnt = [0] * B
    startT = [0] * S
    bt = [0] * S
    dep = []
    ai = 0
    makespan = 0

    while ai < S or dep:
        if ai < S:
            t = AS[ai]
            if dep:
                d = dep[0] >> 12
                if d < t:
                    t = d
        else:
            t = dep[0] >> 12

        # 1. departures at t
        while dep and (dep[0] >> 12) == t:
            b = heappop(dep) & 4095
            heappush(FB[bcls[b]], b)

        # 2. arrivals at t
        while ai < S and AS[ai] == t:
            r = arr_order[ai]
            heappush(H[SZ[r]], r)
            ai += 1

        # 3. assignment, class by class, berth index ascending
        for c in (1, 2, 3):
            fb = FB[c]
            while fb:
                best = -1
                bz = 0
                for z in range(1, c + 1):
                    h = H[z]
                    if h:
                        if best < 0 or h[0] < best:
                            best = h[0]
                            bz = z
                if best < 0:
                    break
                b = heappop(fb)
                r = heappop(H[bz])
                setup = 1 if last[b] == OP[r] else 4
                rate = brate[b]
                svc = (CG[r] + rate - 1) // rate + setup
                last[b] = OP[r]
                startT[r] = t
                bt[r] = b
                busy[b] += svc
                cnt[b] += 1
                e = t + svc
                if e > makespan:
                    makespan = e
                heappush(dep, (e << 12) | b)

    # statistics and digest in ascending ID order
    idx = sorted(range(S), key=lambda r: ID[r])
    g = 0
    W = 0
    mx = -1
    mxid = -1
    MOD = 1000000007
    for r in idx:
        st = startT[r]
        w = st - ARR[r]
        W += w
        if w > mx:
            mx = w
            mxid = ID[r]
        g = (g * 1000003 + st * 31 + bt[r]) % MOD

    out = []
    out.append("ships %d" % S)
    out.append("makespan %d" % makespan)
    out.append("wait total %d max %d ship %d" % (W, mx, mxid))
    for b in range(B):
        out.append("berth %d ships %d busy %d" % (b, cnt[b], busy[b]))
    out.append("digest %d" % g)
    sys.stdout.write("\n".join(out) + "\n")


main()
