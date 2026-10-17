import heapq
import sys
from typing import TextIO


def read_ints(data: TextIO) -> list[int]:
    return [int(tok) for tok in data.read().split()]


def prim_mst_weight(n: int, adj: list[list[tuple[int, int]]]) -> int:
    in_tree = [False] * n
    best = [None] * n
    heap: list[tuple[int, int]] = [(0, 0)]
    total = 0
    count = 0
    while heap and count < n:
        w, u = heapq.heappop(heap)
        if in_tree[u]:
            continue
        in_tree[u] = True
        total += w
        count += 1
        for v, ew in adj[u]:
            if not in_tree[v] and (best[v] is None or ew < best[v]):
                best[v] = ew
                heapq.heappush(heap, (ew, v))
    return total


def main() -> None:
    data = sys.stdin
    nums = read_ints(data)
    it = iter(nums)
    n = next(it)
    m = next(it)
    adj: list[list[tuple[int, int]]] = [[] for _ in range(n)]
    for _ in range(m):
        a = next(it)
        b = next(it)
        w = next(it)
        adj[a].append((b, w))
        adj[b].append((a, w))
    print(prim_mst_weight(n, adj))


if __name__ == "__main__":
    main()
