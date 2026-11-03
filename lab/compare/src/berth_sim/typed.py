from ail import heappop, heappush
import sys

class Fr:

    def __init__(self, a: list[int], b: list[int], c: list[int]):
        self.a = a
        self.b = b
        self.c = c

def fpush(s: Fr, cl: int, x: int) -> None:
    if cl == 1:
        heappush(s.a, x)
    elif cl == 2:
        heappush(s.b, x)
    else:
        heappush(s.c, x)

def fempty(s: Fr, cl: int) -> bool:
    if cl == 1:
        return len(s.a) == 0
    elif cl == 2:
        return len(s.b) == 0
    return len(s.c) == 0

def fpop(s: Fr, cl: int) -> int:
    if cl == 1:
        return heappop(s.a)
    elif cl == 2:
        return heappop(s.b)
    return heappop(s.c)

def main() -> int:
    first = input().split(' ')
    nb = int(first[0])
    ns = int(first[1])
    cls: list[int] = []
    rate: list[int] = []
    for b in range(nb):
        f = input().split(' ')
        cls.append(int(f[0]))
        rate.append(int(f[1]))
    ids: list[int] = []
    arr: list[int] = []
    sz: list[int] = []
    cg: list[int] = []
    pr: list[int] = []
    op: list[int] = []
    for line in sys.stdin:
        f = line.split(' ')
        ids.append(int(f[0]))
        arr.append(int(f[1]))
        sz.append(int(f[2]))
        cg.append(int(f[3]))
        pr.append(int(f[4]))
        op.append(int(f[5]))
    n = len(ids)
    keys: list[int] = [arr[i] * 1073741824 + ids[i] for i in range(n)]
    ord = [i for i in range(n)]
    ord.sort(key=lambda i: keys[i])
    # rank r -> original index ord[r]
    m = n + 1
    start = [0] * n
    berthof = [0] * n
    lastop = [-1] * nb
    bn = [0] * nb
    bbusy = [0] * nb
    w1: list[int] = []
    w2: list[int] = []
    w3: list[int] = []
    fr = Fr([], [], [])
    for b in range(nb):
        fpush(fr, cls[b], b)
    dep: list[int] = []
    p = 0
    makespan = 0
    done = 0
    wtot = 0
    wmax = -1
    wid = -1
    while p < n or len(dep) > 0:
        t = 0
        if p < n and (len(dep) == 0 or arr[ord[p]] <= dep[0] // 2048):
            t = arr[ord[p]]
        else:
            t = dep[0] // 2048
        while len(dep) > 0 and dep[0] // 2048 == t:
            d = heappop(dep)
            b = d % 2048
            fpush(fr, cls[b], b)
        while p < n and arr[ord[p]] == t:
            o = ord[p]
            k = pr[o] * m + p
            if sz[o] == 1:
                heappush(w1, k)
            elif sz[o] == 2:
                heappush(w2, k)
            else:
                heappush(w3, k)
            p += 1
        for c in range(1, 4):
            while not fempty(fr, c):
                best = -1
                which = 0
                if len(w1) > 0:
                    best = w1[0]
                    which = 1
                if c >= 2 and len(w2) > 0 and (best < 0 or w2[0] < best):
                    best = w2[0]
                    which = 2
                if c >= 3 and len(w3) > 0 and (best < 0 or w3[0] < best):
                    best = w3[0]
                    which = 3
                if best < 0:
                    break
                if which == 1:
                    heappop(w1)
                elif which == 2:
                    heappop(w2)
                else:
                    heappop(w3)
                b = fpop(fr, c)
                r = best % m
                o = ord[r]
                setup = 4
                if lastop[b] == op[o]:
                    setup = 1
                lastop[b] = op[o]
                st = (cg[o] + rate[b] - 1) // rate[b] + setup
                start[r] = t
                berthof[r] = b
                bn[b] += 1
                bbusy[b] += st
                wt = t - arr[o]
                wtot += wt
                if wt > wmax or (wt == wmax and ids[o] < wid):
                    wmax = wt
                    wid = ids[o]
                e = t + st
                if e > makespan:
                    makespan = e
                heappush(dep, e * 2048 + b)
    print(f'ships {n}')
    print(f'makespan {makespan}')
    if n == 0:
        print('wait total 0 max 0 ship -1')
    else:
        print(f'wait total {wtot} max {wmax} ship {wid}')
    for b in range(nb):
        print(f'berth {b} ships {bn[b]} busy {bbusy[b]}')
    byid = [i for i in range(n)]
    byid.sort(key=lambda r: ids[ord[r]])
    g = 0
    for r in byid:
        g = (g * 1000003 + start[r] * 31 + berthof[r]) % 1000000007
    print(f'digest {g}')
    return 0

if __name__ == "__main__":
    sys.exit(main())
