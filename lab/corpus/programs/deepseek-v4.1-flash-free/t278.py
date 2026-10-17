import sys
import heapq


def main() -> None:
    data = sys.stdin.buffer.read().split()
    if not data:
        return
    it = iter(data)
    n = int(next(it))
    m = int(next(it))

    adj: list[list[tuple[int, int]]] = [[] for _ in range(n)]
    for _ in range(m):
        a = int(next(it))
        b = int(next(it))
        w = int(next(it))
        adj[a].append((w, b))
        adj[b].append((w, a))

    visited = [False] * n
    total = 0
    count = 0
    heap: list[tuple[int, int]] = []

    if n > 0:
        visited[0] = True
        count = 1
        for w, b in adj[0]:
            heapq.heappush(heap, (w, b))

        while heap and count < n:
            w, v = heapq.heappop(heap)
            if visited[v]:
                continue
            visited[v] = True
            count += 1
            total += w
            for nw, nb in adj[v]:
                if not visited[nb]:
                    heapq.heappush(heap, (nw, nb))

    sys.stdout.write(str(total) + "\n")


if __name__ == "__main__":
    main()
