from ail import heappop, heappush
import sys

class Item:

    def __init__(self, d: int, b: int, n: int):
        self.d = d
        self.b = b
        self.n = n

class G:

    def __init__(self, nn: int, ns: int, x: list[int], sstart: list[int], nstation: list[int], estart: list[int], etarget: list[int], ecost: list[int], dt: list[int], db: list[int], done: list[int], t0: list[int], t1: list[int], h0: list[Item], h1: list[Item], mt: int, mb: int):
        self.nn = nn
        self.ns = ns
        self.x = x
        self.sstart = sstart
        self.nstation = nstation
        self.estart = estart
        self.etarget = etarget
        self.ecost = ecost
        self.dt = dt
        self.db = db
        self.done = done
        self.t0 = t0
        self.t1 = t1
        self.h0 = h0
        self.h1 = h1
        self.mt = mt
        self.mb = mb

def meet(g: G, d: int, node: int) -> None:
    v = g.ns + g.nn
    o = 1 - d
    ot = g.dt[o * v + node]
    if ot >= 0:
        t = g.dt[d * v + node] + ot
        b = g.db[d * v + node] + g.db[o * v + node]
        if t < g.mt or (t == g.mt and b < g.mb):
            g.mt = t
            g.mb = b

def relax(g: G, d: int, node: int, T: int, B: int) -> None:
    v = g.ns + g.nn
    idx = d * v + node
    if g.dt[idx] < 0:
        if d == 0:
            g.t0.append(node)
        else:
            g.t1.append(node)
    if g.dt[idx] < 0 or T < g.dt[idx] or (T == g.dt[idx] and B < g.db[idx]):
        g.dt[idx] = T
        g.db[idx] = B
        if d == 0:
            heappush(g.h0, Item(T, B, node), key=lambda it: (it.d, it.b, it.n))
        else:
            heappush(g.h1, Item(T, B, node), key=lambda it: (it.d, it.b, it.n))
        meet(g, d, node)

def solve(g: G, s: int, t: int) -> str:
    if s == t:
        return '0 0'
    v = g.ns + g.nn
    t0: list[int] = []
    t1: list[int] = []
    h0: list[Item] = []
    h1: list[Item] = []
    g.t0 = t0
    g.t1 = t1
    g.h0 = h0
    g.h1 = h1
    g.mt = 1 << 62
    g.mb = 0
    relax(g, 0, s, 0, 0)
    for n in range(g.sstart[s], g.sstart[s + 1]):
        relax(g, 0, g.ns + n, 0, 1)
    relax(g, 1, t, 0, 0)
    for n in range(g.sstart[t], g.sstart[t + 1]):
        relax(g, 1, g.ns + n, 0, 0)
    while len(g.h0) > 0 and len(g.h1) > 0:
        f = g.h0[0]
        b = g.h1[0]
        if g.mt != 1 << 62:
            st = f.d + b.d
            sb = f.b + b.b
            if st > g.mt or (st == g.mt and sb >= g.mb):
                break
        d = 0
        if len(g.h0) > len(g.h1):
            d = 1
        it = Item(0, 0, 0)
        if d == 0:
            it = heappop(g.h0, key=lambda it: (it.d, it.b, it.n))
        else:
            it = heappop(g.h1, key=lambda it: (it.d, it.b, it.n))
        u = it.n
        idx = d * v + u
        if g.done[idx] != 0 or it.d != g.dt[idx] or it.b != g.db[idx]:
            continue
        g.done[idx] = 1
        if u < g.ns:
            if d == 0:
                nd = it.d + g.x[u]
                nb = it.b + 1
                for n in range(g.sstart[u], g.sstart[u + 1]):
                    w = g.ns + n
                    if g.done[w] == 0:
                        relax(g, 0, w, nd, nb)
            else:
                for n in range(g.sstart[u], g.sstart[u + 1]):
                    w = g.ns + n
                    if g.done[v + w] == 0:
                        relax(g, 1, w, it.d, it.b)
        else:
            k = u - g.ns
            hub = g.nstation[k]
            if g.done[d * v + hub] == 0:
                if d == 0:
                    relax(g, 0, hub, it.d, it.b)
                else:
                    relax(g, 1, hub, it.d + g.x[hub], it.b + 1)
            for e in range(g.estart[k], g.estart[k + 1]):
                w = g.etarget[e]
                if g.done[d * v + w] == 0:
                    nd = it.d + g.ecost[e]
                    if d == 0:
                        relax(g, 0, w, nd, it.b)
                    else:
                        relax(g, 1, w, nd, it.b)
    for id in g.t0:
        g.dt[id] = -1
        g.done[id] = 0
    for id in g.t1:
        g.dt[v + id] = -1
        g.done[v + id] = 0
    if g.mt == 1 << 62:
        return 'none'
    return f'{g.mt} {g.mb}'

def main() -> int:
    first = input().split()
    n = int(first[0])
    m = int(first[1])
    q = int(first[2])
    x: list[int] = []
    for w in input().split():
        x.append(int(w))
    eu = [0] * m
    ev = [0] * m
    el = [0] * m
    et = [0] * m
    cnt = [0] * (n + 1)
    for i in range(m):
        f = input().split()
        eu[i] = int(f[0])
        ev[i] = int(f[1])
        el[i] = int(f[2])
        et[i] = int(f[3])
        cnt[eu[i] + 1] += 1
        cnt[ev[i] + 1] += 1
    # half-edge h: 2i = u->v, 2i+1 = v->u ; source station of h
    for i in range(n):
        cnt[i + 1] += cnt[i]
    pos = [0] * n
    for i in range(n):
        pos[i] = cnt[i]
    hs = [0] * (2 * m)
    for i in range(m):
        hs[pos[eu[i]]] = 2 * i
        pos[eu[i]] += 1
        hs[pos[ev[i]]] = 2 * i + 1
        pos[ev[i]] += 1
    stamp = [-1] * 100000
    lastid = [0] * 100000
    nodeof = [0] * (2 * m)
    sstart = [0] * (n + 1)
    nstation: list[int] = []
    k = 0
    for v in range(n):
        sstart[v] = k
        for j in range(cnt[v], cnt[v + 1]):
            hh = hs[j]
            l = el[hh // 2]
            if stamp[l] != v:
                stamp[l] = v
                lastid[l] = k
                nstation.append(v)
                k += 1
            nodeof[hh] = lastid[l]
    sstart[n] = k
    estart = [0] * (k + 1)
    for hh in range(2 * m):
        estart[nodeof[hh] + 1] += 1
    for i in range(k):
        estart[i + 1] += estart[i]
    epos = [0] * k
    for i in range(k):
        epos[i] = estart[i]
    etarget = [0] * (2 * m)
    ecost = [0] * (2 * m)
    for hh in range(2 * m):
        a = nodeof[hh]
        etarget[epos[a]] = n + nodeof[hh ^ 1]
        ecost[epos[a]] = et[hh // 2]
        epos[a] += 1
    inf = 1 << 62
    nv = n + k
    g = G(k, n, x, sstart, nstation, estart, etarget, ecost, [-1] * (2 * nv), [0] * (2 * nv), [0] * (2 * nv), [], [], [], [], inf, 0)
    for _ in range(q):
        f = input().split()
        print(solve(g, int(f[0]), int(f[1])))
    return 0

if __name__ == "__main__":
    sys.exit(main())
