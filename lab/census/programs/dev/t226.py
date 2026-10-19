import sys
from collections import deque


def main() -> None:
    data = sys.stdin.read().split()
    if len(data) < 2:
        print(-1)
        return

    h = int(data[0])
    w = int(data[1])
    rows: list[str] = data[2:2 + h]
    # Pad missing rows/columns with walls so bounds handling stays simple.
    rows += ["#" * w] * (h - len(rows))
    rows = [r.ljust(w, "#")[:w] for r in rows]

    start: tuple[int, int] | None = None
    end: tuple[int, int] | None = None
    for r in range(h):
        for c in range(w):
            ch = rows[r][c]
            if ch == "S":
                start = (r, c)
            elif ch == "E":
                end = (r, c)

    if start is None or end is None:
        print(-1)
        return

    dist: list[list[int]] = [[-1] * w for _ in range(h)]
    dist[start[0]][start[1]] = 0
    queue: deque[tuple[int, int]] = deque([start])

    directions = [
        (-1, -1), (-1, 0), (-1, 1),
        (0, -1),           (0, 1),
        (1, -1),  (1, 0),  (1, 1),
    ]

    while queue:
        r, c = queue.popleft()
        if (r, c) == end:
            print(dist[r][c])
            return
        for dr, dc in directions:
            nr, nc = r + dr, c + dc
            if 0 <= nr < h and 0 <= nc < w:
                if rows[nr][nc] != "#" and dist[nr][nc] == -1:
                    dist[nr][nc] = dist[r][c] + 1
                    queue.append((nr, nc))

    print(-1)


if __name__ == "__main__":
    main()
