import sys
import heapq


def find(parent: list[int], a: int) -> int:
    while parent[a] != a:
        parent[a] = parent[parent[a]]
        a = parent[a]
    return a


def read_ints() -> list[int]:
    buf: bytes = sys.stdin.buffer.read()
    data: list[int] = []
    num: int = 0
    innum: bool = False
    for c in buf:
        if c >= 48 and c <= 57:
            num = num * 10 + (c - 48)
            innum = True
        elif innum:
            data.append(num)
            num = 0
            innum = False
    if innum:
        data.append(num)
    return data


def main() -> None:
    data: list[int] = read_ints()
    if len(data) < 3:
        return

    n: int = data[0]
    m: int = data[1]
    q: int = data[2]

    xoff: int = 3
    eoff: int = xoff + n
    xvals: list[int] = data[xoff:eoff]

    deg: list[int] = [0] * n
    parent: list[int] = list(range(n))

    for i in range(m):
        base: int = eoff + 4 * i
        u: int = data[base]
        v: int = data[base + 1]
        deg[u] += 1
        deg[v] += 1
        ru: int = find(parent, u)
        rv: int = find(parent, v)
        if ru != rv:
            parent[ru] = rv

    head: list[int] = [0] * (n + 1)
    for i in range(n):
        head[i + 1] = head[i] + deg[i]

    pos: list[int] = head[:n]
    arcs: int = head[n]
    to: list[int] = [0] * arcs
    aline: list[int] = [0] * arcs
    atime: list[int] = [0] * arcs

    for i in range(m):
        base: int = eoff + 4 * i
        u: int = data[base]
        v: int = data[base + 1]
        l: int = data[base + 2]
        t: int = data[base + 3]
        p: int = pos[u]
        to[p] = v
        aline[p] = l
        atime[p] = t
        pos[u] = p + 1
        p = pos[v]
        to[p] = u
        aline[p] = l
        atime[p] = t
        pos[v] = p + 1

    qoff: int = eoff + 4 * m
    queries: list[int] = data[qoff:qoff + 2 * q]

    del data
    del deg
    del pos

    lmax: int = 100001
    sent: int = 100000
    limit: int = 1 << 62

    out: list[str] = []

    for qi in range(q):
        s: int = queries[2 * qi]
        d: int = queries[2 * qi + 1]

        if s == d:
            out.append("0 0")
            continue

        if find(parent, s) != find(parent, d):
            out.append("none")
            continue

        dist_t: dict[int, int] = {}
        dist_b: dict[int, int] = {}

        start_key: int = s * lmax + sent
        dist_t[start_key] = 0
        dist_b[start_key] = 0

        heap: list[tuple[int, int, int]] = [(0, 0, start_key)]
        ans_t: int = -1
        ans_b: int = 0

        while len(heap) > 0:
            ent: tuple[int, int, int] = heapq.heappop(heap)
            ct: int = ent[0]
            cb: int = ent[1]
            key: int = ent[2]

            if key not in dist_t:
                continue
            if dist_t[key] != ct or dist_b[key] != cb:
                continue

            st: int = key // lmax
            ln: int = key % lmax

            if st == d:
                ans_t = ct
                ans_b = cb
                break

            xu: int = xvals[st]
            aidx: int = head[st]
            aend: int = head[st + 1]

            while aidx < aend:
                v: int = to[aidx]
                l2: int = aline[aidx]
                w: int = atime[aidx]

                nt: int = 0
                nb: int = 0
                if l2 == ln:
                    nt = ct + w
                    nb = cb
                elif ln == sent:
                    nt = ct + w
                    nb = cb + 1
                else:
                    nt = ct + w + xu
                    nb = cb + 1

                if nt <= limit:
                    nkey: int = v * lmax + l2
                    if nkey in dist_t:
                        ot: int = dist_t[nkey]
                        ob: int = dist_b[nkey]
                        if nt < ot or (nt == ot and nb < ob):
                            dist_t[nkey] = nt
                            dist_b[nkey] = nb
                            heapq.heappush(heap, (nt, nb, nkey))
                    else:
                        dist_t[nkey] = nt
                        dist_b[nkey] = nb
                        heapq.heappush(heap, (nt, nb, nkey))

                aidx += 1

        if ans_t < 0:
            out.append("none")
        else:
            out.append(str(ans_t) + " " + str(ans_b))

    if len(out) > 0:
        sys.stdout.write("\n".join(out))
        sys.stdout.write("\n")


main()
