import sys
from collections import deque


def main() -> None:
    data = sys.stdin.read().split()
    if not data:
        return
    n = int(data[0])
    m = int(data[1]) if len(data) > 1 else 0

    adj: list[list[int]] = [[] for _ in range(n)]
    idx = 2
    for _ in range(m):
        if idx + 1 >= len(data):
            break
        a = int(data[idx])
        b = int(data[idx + 1])
        idx += 2
        adj[a].append(b)
        adj[b].append(a)

    dist: list[int] = [-1] * n
    count: list[int] = [0] * n
    dist[0] = 0
    count[0] = 1
    queue: deque[int] = deque([0])

    while queue:
        u = queue.popleft()
        for v in adj[u]:
            if dist[v] == -1:
                dist[v] = dist[u] + 1
                count[v] = count[u]
                queue.append(v)
            elif dist[v] == dist[u] + 1:
                count[v] += count[u]

    print(" ".join(str(c) for c in count))


if __name__ == "__main__":
    main()
