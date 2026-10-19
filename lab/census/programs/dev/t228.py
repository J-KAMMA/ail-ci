import sys
from collections import deque


def main() -> None:
    data = sys.stdin.read().split()
    if len(data) < 2:
        return
    h = int(data[0])
    w = int(data[1])
    rows: list[str] = data[2:2 + h]
    # Pad any missing rows or short rows so indexing is safe.
    grid: list[str] = []
    for r in range(h):
        line = rows[r] if r < len(rows) else ""
        if len(line) < w:
            line = line + "." * (w - len(line))
        grid.append(line[:w])

    visited = [[False] * w for _ in range(h)]
    sizes: list[int] = []

    neighbors = [
        (-1, -1), (-1, 0), (-1, 1),
        (0, -1),           (0, 1),
        (1, -1),  (1, 0),  (1, 1),
    ]

    for i in range(h):
        for j in range(w):
            if grid[i][j] != '#' or visited[i][j]:
                continue
            visited[i][j] = True
            queue: deque[tuple[int, int]] = deque([(i, j)])
            count = 0
            while queue:
                ci, cj = queue.popleft()
                count += 1
                for di, dj in neighbors:
                    ni, nj = ci + di, cj + dj
                    if 0 <= ni < h and 0 <= nj < w:
                        if grid[ni][nj] == '#' and not visited[ni][nj]:
                            visited[ni][nj] = True
                            queue.append((ni, nj))
            sizes.append(count)

    sizes.sort(reverse=True)
    for s in sizes:
        print(s)


if __name__ == "__main__":
    main()
