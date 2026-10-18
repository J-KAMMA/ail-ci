import sys
from collections import deque


def solve(h: int, w: int, grid: list[str]) -> str:
    sr = sc = er = ec = 0
    for r in range(h):
        for c in range(w):
            if grid[r][c] == 'S':
                sr, sc = r, c
            elif grid[r][c] == 'E':
                er, ec = r, c

    visited = [[False] * w for _ in range(h)]
    visited[sr][sc] = True
    q: deque[tuple[int, int]] = deque([(sr, sc)])
    while q:
        r, c = q.popleft()
        for dr, dc in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            nr, nc = r + dr, c + dc
            if 0 <= nr < h and 0 <= nc < w and not visited[nr][nc] and grid[nr][nc] != '#':
                visited[nr][nc] = True
                q.append((nr, nc))

    count = 0
    out: list[str] = []
    for r in range(h):
        row: list[str] = []
        for c in range(w):
            ch = grid[r][c]
            if ch in 'SE':
                row.append(ch)
            elif visited[r][c] and ch != '#':
                row.append('+')
                count += 1
            else:
                row.append(ch)
        out.append(''.join(row))
    return '\n'.join(out) + '\n' + str(count)


def main() -> None:
    data = sys.stdin.read().split('\n')
    h, w = map(int, data[0].split())
    grid = [data[i + 1][:w] for i in range(h)]
    sys.stdout.write(solve(h, w, grid))


if __name__ == "__main__":
    main()
