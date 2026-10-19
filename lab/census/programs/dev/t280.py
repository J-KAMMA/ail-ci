import heapq
import sys
from typing import List, Tuple


def main() -> None:
    data = sys.stdin.read().split()
    if not data:
        return
    idx = 0
    n = int(data[idx]); idx += 1
    m = int(data[idx]); idx += 1

    adj: List[List[Tuple[int, int]]] = [[] for _ in range(n)]
    for _ in range(m):
        a = int(data[idx]); b = int(data[idx + 1]); w = int(data[idx + 2])
        idx += 3
        adj[a].append((b, w))
        adj[b].append((a, w))

    INF = float("inf")
    d1: List[float] = [INF] * n
    d2: List[float] = [INF] * n
    d1[0] = 0
    heap: List[Tuple[float, int]] = [(0, 0)]

    while heap:
        d, u = heapq.heappop(heap)
        if d != d1[u] and d != d2[u]:
            continue
        for v, w in adj[u]:
            nd = d + w
            if nd < d1[v]:
                old = d1[v]
                d2[v] = old
                d1[v] = nd
                heapq.heappush(heap, (nd, v))
                if old < INF:
                    heapq.heappush(heap, (old, v))
            elif d1[v] < nd < d2[v]:
                d2[v] = nd
                heapq.heappush(heap, (nd, v))

    result = d2[n - 1]
    if result == INF:
        print(-1)
    else:
        print(int(result))


if __name__ == "__main__":
    main()
