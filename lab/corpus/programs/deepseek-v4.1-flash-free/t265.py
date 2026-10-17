import sys
from collections import deque


def main() -> None:
    data = sys.stdin.buffer.read().split()
    idx = 0
    n = int(data[idx])
    idx += 1
    m = int(data[idx])
    idx += 1

    adj: list[list[int]] = [[] for _ in range(n)]
    for _ in range(m):
        a = int(data[idx])
        idx += 1
        b = int(data[idx])
        idx += 1
        adj[a].append(b)
        adj[b].append(a)

    dist: list[int] = [-1] * n
    order: list[int] = []
    dist[0] = 0
    queue: deque[int] = deque([0])

    while queue:
        u = queue.popleft()
        order.append(u)
        for v in adj[u]:
            if dist[v] == -1:
                dist[v] = dist[u] + 1
                queue.append(v)

    lines: list[str] = []
    lines.append(" ".join(map(str, order)))
    for v in range(n):
        lines.append(f"{v} {dist[v]}")

    sys.stdout.write("\n".join(lines) + "\n")


if __name__ == "__main__":
    main()
