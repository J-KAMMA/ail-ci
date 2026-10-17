import sys
import heapq


def main() -> None:
    data = sys.stdin.read().split()
    h, w = int(data[0]), int(data[1])
    grid = [[int(c) for c in data[2 + i]] for i in range(h)]

    INF = float("inf")
    dist: list[list[float]] = [[INF] * w for _ in range(h)]
    dist[0][0] = 0

    pq: list[tuple[int, int, int]] = [(0, 0, 0)]
    while pq:
        d, r, c = heapq.heappop(pq)
        if d > dist[r][c]:
            continue
        if r == h - 1 and c == w - 1:
            print(d)
            return
        for nr, nc in ((r - 1, c), (r + 1, c), (r, c - 1), (r, c + 1)):
            if 0 <= nr < h and 0 <= nc < w:
                nd = d + grid[nr][nc]
                if nd < dist[nr][nc]:
                    dist[nr][nc] = nd
                    heapq.heappush(pq, (nd, nr, nc))

    print(int(dist[h - 1][w - 1]))


if __name__ == "__main__":
    main()
