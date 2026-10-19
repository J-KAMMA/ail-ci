from collections import deque
import sys


def main() -> None:
    data = sys.stdin.read().split()
    if not data:
        return
    idx = 0
    n = int(data[idx])
    idx += 1
    m = int(data[idx]) if idx < len(data) else 0
    idx += 1

    adj: list[list[tuple[int, int]]] = [[] for _ in range(n)]
    for _ in range(m):
        if idx + 2 >= len(data) + 0 and idx + 2 > len(data) - 1:
            break
        a = int(data[idx])
        b = int(data[idx + 1])
        w = int(data[idx + 2])
        idx += 3
        if 0 <= a < n and 0 <= b < n:
            adj[a].append((b, w))

    dist: list[int] = [-1] * n
    total_weight = 0
    if n > 0:
        dist[0] = 0
        queue: deque[int] = deque([0])
        while queue:
            u = queue.popleft()
            for v, w in adj[u]:
                if dist[v] == -1:
                    dist[v] = dist[u] + 1
                    total_weight += w
                    queue.append(v)

    print(" ".join(str(d) for d in dist))
    print(total_weight)


if __name__ == "__main__":
    main()
