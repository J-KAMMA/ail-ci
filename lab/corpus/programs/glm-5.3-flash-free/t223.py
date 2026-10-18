import sys
from collections import deque


def count_components(grid: list[str], h: int, w: int) -> tuple[int, int]:
    visited = [[False] * w for _ in range(h)]
    components = 0
    largest = 0
    for sr in range(h):
        for sc in range(w):
            if grid[sr][sc] != "#" and not visited[sr][sc]:
                components += 1
                size = 0
                queue: deque[tuple[int, int]] = deque([(sr, sc)])
                visited[sr][sc] = True
                while queue:
                    r, c = queue.popleft()
                    size += 1
                    for dr, dc in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                        nr, nc = r + dr, c + dc
                        if 0 <= nr < h and 0 <= nc < w and grid[nr][nc] != "#" and not visited[nr][nc]:
                            visited[nr][nc] = True
                            queue.append((nr, nc))
                if size > largest:
                    largest = size
    return components, largest


def main() -> None:
    data = sys.stdin.read().split("\n")
    h, w = map(int, data[0].split())
    grid = [line.rstrip() for line in data[1 : 1 + h]]
    components, largest = count_components(grid, h, w)
    print(f"{components} {largest}")


if __name__ == "__main__":
    main()
