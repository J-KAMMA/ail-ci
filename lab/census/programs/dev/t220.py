import sys
from collections import deque


def main() -> None:
    data = sys.stdin.read().split()
    if len(data) < 2:
        print(-1)
        return

    h = int(data[0])
    w = int(data[1])
    rows = data[2:2 + h]

    # Normalize rows to exactly w characters, treating missing cells as walls.
    grid: list[str] = [row.ljust(w, "#")[:w] for row in rows]
    while len(grid) < h:
        grid.append("#" * w)

    start: tuple[int, int] | None = None
    end: tuple[int, int] | None = None
    for r in range(h):
        for c in range(w):
            ch = grid[r][c]
            if ch == "S":
                start = (r, c)
            elif ch == "E":
                end = (r, c)

    if start is None or end is None:
        print(-1)
        return

    if start == end:
        print(0)
        return

    dist: list[list[int]] = [[-1] * w for _ in range(h)]
    dist[start[0]][start[1]] = 0
    queue: deque[tuple[int, int]] = deque([start])
    directions = ((1, 0), (-1, 0), (0, 1), (0, -1))

    while queue:
        r, c = queue.popleft()
        d = dist[r][c]
        for dr, dc in directions:
            nr, nc = r + dr, c + dc
            if 0 <= nr < h and 0 <= nc < w and dist[nr][nc] == -1:
                ch = grid[nr][nc]
                if ch == "#":
                    continue
                dist[nr][nc] = d + 1
                if (nr, nc) == end:
                    print(d + 1)
                    return
                queue.append((nr, nc))

    print(-1)


if __name__ == "__main__":
    main()
