import sys

def main() -> None:
    data = sys.stdin.buffer.read().split()
    if not data:
        return
    it = iter(data)
    n = int(next(it))
    m = int(next(it))

    head = [-1] * n
    to = []
    nxt = []

    def add_edge(u: int, v: int) -> None:
        to.append(v)
        nxt.append(head[u])
        head[u] = len(to) - 1

    for _ in range(m):
        a = int(next(it))
        b = int(next(it))
        add_edge(a, b)
        add_edge(b, a)

    sys.setrecursionlimit(max(1000, n * 2 + 10))

    disc = [0] * n
    low = [0] * n
    visited = [False] * n
    timer = 0
    bridges = []

    def dfs(u: int, parent_edge: int) -> None:
        nonlocal timer
        visited[u] = True
        timer += 1
        disc[u] = low[u] = timer
        e = head[u]
        while e != -1:
            v = to[e]
            if e == (parent_edge ^ 1):
                e = nxt[e]
                continue
            if visited[v]:
                if disc[v] < low[u]:
                    low[u] = disc[v]
            else:
                dfs(v, e)
                if low[v] < low[u]:
                    low[u] = low[v]
                if low[v] > disc[u]:
                    bridges.append((u, v))
            e = nxt[e]

    for s in range(n):
        if not visited[s]:
            dfs(s, -1)

    result = []
    for u, v in bridges:
        if u > v:
            u, v = v, u
        result.append((u, v))
    result.sort()

    out = [str(len(result))]
    out.extend(f"{u} {v}" for u, v in result)
    sys.stdout.write("\n".join(out) + "\n")

if __name__ == "__main__":
    main()
