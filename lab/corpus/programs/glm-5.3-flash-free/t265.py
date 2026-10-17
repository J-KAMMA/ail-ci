import sys
from collections import deque


def bfs(n: int, adj: list[list[int]]) -> tuple[list[int], list[int]]:
    order: list[int] = []
    dist: list[int] = [-1] * n
    dist[0] = 0
    queue: deque[int] = deque([0])
    while queue:
        u = queue.popleft()
        order.append(u)
        for v in adj[u]:
            if dist[v] == -1:
                dist[v] = dist[u] + 1
                queue.append(v)
    return order, dist


def main() -> None:
    data = sys.stdin.buffer.read().split()
    n = int(data[0])
    m = int(data[1])
    adj: list[list[int]] = [[] for _ in range(n)]
    idx = 2
    for _ in range(m):
        a = int(data[idx])
        b = int(data[idx + 1])
        idx += 2
        adj[a].append(b)
        adj[b].append(a)
    order, dist = bfs(n, adj)
    out: list[str] = [" ".join(map(str, order))]
    out.extend(f"{i} {dist[i]}" for i in range(n))
    sys.stdout.write("\n".join(out) + "\n")


if __name__ == "__main__":
    main()
