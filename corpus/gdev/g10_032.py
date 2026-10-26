# task: Write a script that computes the size of the largest connected region of ones in a hardcoded binary matrix using BFS and prints it.
from collections import deque


GRID: list[list[int]] = [
    [1, 1, 0, 0, 1, 0, 0, 0],
    [1, 0, 0, 1, 1, 0, 1, 0],
    [0, 0, 0, 1, 0, 0, 1, 1],
    [1, 1, 0, 0, 0, 1, 0, 1],
    [1, 0, 1, 1, 0, 1, 1, 0],
    [0, 0, 0, 1, 0, 0, 0, 0],
    [1, 1, 0, 1, 1, 1, 0, 1],
    [0, 1, 0, 0, 0, 1, 1, 1],
]


def largest_region(grid: list[list[int]]) -> int:
    """Return the size of the largest 4-connected region of ones using BFS."""
    if not grid or not grid[0]:
        return 0

    rows = len(grid)
    cols = len(grid[0])
    visited = [[False] * cols for _ in range(rows)]
    best = 0
    directions = ((-1, 0), (1, 0), (0, -1), (0, 1))

    for r in range(rows):
        for c in range(cols):
            if grid[r][c] != 1 or visited[r][c]:
                continue

            visited[r][c] = True
            queue: deque[tuple[int, int]] = deque([(r, c)])
            size = 0

            while queue:
                cr, cc = queue.popleft()
                size += 1
                for dr, dc in directions:
                    nr, nc = cr + dr, cc + dc
                    if (
                        0 <= nr < rows
                        and 0 <= nc < cols
                        and grid[nr][nc] == 1
                        and not visited[nr][nc]
                    ):
                        visited[nr][nc] = True
                        queue.append((nr, nc))

            best = max(best, size)

    return best


def main() -> None:
    size = largest_region(GRID)
    print(f"Largest connected region of ones: {size}")


if __name__ == "__main__":
    main()
