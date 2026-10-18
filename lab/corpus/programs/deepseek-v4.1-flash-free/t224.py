import sys
from collections import deque


def main() -> None:
    data = sys.stdin.read().split()
    if not data:
        return
    h = int(data[0])
    w = int(data[1])
    grid = [list(data[2 + i]) for i in range(h)]

    start = None
    for i in range(h):
        for j in range(w):
            if grid[i][j] == 'S':
                start = (i, j)
    if start is None:
        return

    visited = [[False] * w for _ in range(h)]
    sr, sc = start
    visited[sr][sc] = True
    queue = deque([start])
    count = 0
    while queue:
        r, c = queue.popleft()
        if grid[r][c] == '.':
            count += 1
        for dr, dc in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            nr, nc = r + dr, c + dc
            if 0 <= nr < h and 0 <= nc < w and not visited[nr][nc]:
                if grid[nr][nc] != '#':
                    visited[nr][nc] = True
                    queue.append((nr, nc))

    for i in range(h):
        for j in range(w):
            if visited[i][j] and grid[i][j] == '.':
                grid[i][j] = '+'

    for row in grid:
        print(''.join(row))
    print(count)


if __name__ == "__main__":
    main()
