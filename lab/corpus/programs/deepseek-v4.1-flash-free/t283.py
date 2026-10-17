import sys
import heapq
from typing import List, Tuple


def dijkstra(source: int, adj: List[List[Tuple[int, int]]], n: int) -> List[int]:
    INF = float("inf")
    dist: List[float] = [INF] * n
    dist[source] = 0
    heap: List[Tuple[int, int]] = [(0, source)]
    while heap:
        d, u = heapq.heappop(heap)
        if d > dist[u]:
            continue
        for v, w in adj[u]:
            nd = d + w
            if nd < dist[v]:
                dist[v] = nd
                heapq.heappush(heap, (nd, v))
    return dist


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

    ecc: List[int] = [0] * n
    for s in range(n):
        dist = dijkstra(s, adj, n)
        best = 0
        for node, d in enumerate(dist):
            if node != s and d > best:
                best = d
        ecc[s] = best

    radius = min(ecc)
    centres = [i for i, e in enumerate(ecc) if e == radius]

    out = [f"Eccentricity of {i}: {e}" for i, e in enumerate(ecc)]
    out.append(f"Radius: {radius}")
    out.append("Centre nodes: " + " ".join(str(c) for c in centres))
    sys.stdout.write("\n".join(out) + "\n")


if __name__ == "__main__":
    main()
