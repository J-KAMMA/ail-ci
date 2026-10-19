import sys
from collections import deque


def main() -> None:
    data = sys.stdin.read().split()
    if not data:
        print(0, 0, 0)
        return

    n = int(data[0])
    m = int(data[1]) if len(data) > 1 else 0

    adj: list[list[int]] = [[] for _ in range(n)]
    indeg: list[int] = [0] * n
    outdeg: list[int] = [0] * n

    idx = 2
    for _ in range(m):
        a = int(data[idx])
        b = int(data[idx + 1])
        idx += 2
        adj[a].append(b)
        indeg[b] += 1
        outdeg[a] += 1

    sources = sum(1 for i in range(n) if indeg[i] == 0)
    sinks = sum(1 for i in range(n) if outdeg[i] == 0)

    # Longest path (in edges) via Kahn's topological processing.
    remaining = indeg[:]
    dist: list[int] = [0] * n
    queue: deque[int] = deque(i for i in range(n) if remaining[i] == 0)
    processed = 0
    while queue:
        u = queue.popleft()
        processed += 1
        for v in adj[u]:
            if dist[u] + 1 > dist[v]:
                dist[v] = dist[u] + 1
            remaining[v] -= 1
            if remaining[v] == 0:
                queue.append(v)

    longest = max(dist) if n > 0 else 0

    print(longest, sources, sinks)


if __name__ == "__main__":
    main()
