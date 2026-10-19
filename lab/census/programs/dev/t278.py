import heapq
import sys


def main() -> None:
    data = sys.stdin.read().split()
    if not data:
        return

    n = int(data[0])
    m = int(data[1]) if len(data) > 1 else 0

    adj: list[list[tuple[int, int]]] = [[] for _ in range(n)]
    idx = 2
    for _ in range(m):
        a = int(data[idx])
        b = int(data[idx + 1])
        w = int(data[idx + 2])
        idx += 3
        adj[a].append((w, b))
        adj[b].append((w, a))

    visited = [False] * n
    heap: list[tuple[int, int]] = [(0, 0)]
    total = 0
    count = 0

    while heap and count < n:
        w, u = heapq.heappop(heap)
        if visited[u]:
            continue
        visited[u] = True
        total += w
        count += 1
        for w2, v in adj[u]:
            if not visited[v]:
                heapq.heappush(heap, (w2, v))

    print(total)


if __name__ == "__main__":
    main()
