import sys
from collections import deque


def main() -> None:
    data = sys.stdin.read().split()
    h = int(data[0])
    w = int(data[1])
    grid: list[list[str]] = [list(data[2 + i]) for i in range(h)]

    # Locate start (S); fall back to top-left if not found.
    start = (0, 0)
    for r in range(h):
        for c in range(len(grid[r])):
            if grid[r][c] == "S":
                start = (r, c)

    visited = [[False] * w for _ in range(h)]
    queue: deque[tuple[int, int]] = deque()
    sr, sc = start
    visited[sr][sc] = True
    queue.append((sr, sc))
    count = 0

    while queue:
        r, c = queue.popleft()
        for dr, dc in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            nr, nc = r + dr, c + dc
            if 0 <= nr < h and 0 <= nc < w and not visited[nr][nc]:
                if nc >= len(grid[nr]):
                    continue
                ch = grid[nr][nc]
                if ch == "#":
                    continue
                visited[nr][nc] = True
                queue.append((nr, nc))
                if ch == ".":
                    grid[nr][nc] = "+"
                    count += 1

    out_lines = ["".join(row) for row in grid]
    out_lines.append(str(count))
    sys.stdout.write("\n".join(out_lines) + "\n")


if __name__ == "__main__":
    main()
