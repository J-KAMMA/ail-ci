# task: Compute the Manhattan distance from every cell to the nearest marked cell in a hard-coded 7x9 grid using multi-source BFS and print the distance grid.
from collections import deque

ROWS: int = 7
COLS: int = 9

# '#' marks a source cell, '.' is an unmarked cell.
GRID: list[str] = [
    "#........",
    ".........",
    ".........",
    "....#....",
    ".........",
    ".#.......",
    "........#",
]

NEIGHBORS: tuple[tuple[int, int], ...] = ((1, 0), (-1, 0), (0, 1), (0, -1))


def multi_source_bfs(grid: list[str]) -> list[list[int]]:
    """Return a grid of Manhattan distances to the nearest '#' cell.

    On an unobstructed grid, 4-directional BFS distance equals Manhattan distance.
    Cells unreachable from any source keep the value -1.
    """
    rows = len(grid)
    cols = len(grid[0]) if rows else 0
    dist: list[list[int]] = [[-1] * cols for _ in range(rows)]
    queue: deque[tuple[int, int]] = deque()

    for r, row in enumerate(grid):
        for c, ch in enumerate(row):
            if ch == "#":
                dist[r][c] = 0
                queue.append((r, c))

    while queue:
        r, c = queue.popleft()
        for dr, dc in NEIGHBORS:
            nr, nc = r + dr, c + dc
            if 0 <= nr < rows and 0 <= nc < cols and dist[nr][nc] == -1:
                dist[nr][nc] = dist[r][c] + 1
                queue.append((nr, nc))

    return dist


def format_grid(dist: list[list[int]]) -> list[str]:
    """Format the distance grid as aligned text rows."""
    max_val = max((max(row) for row in dist), default=0)
    width = max(len(str(max_val)), 1)
    return [" ".join(f"{v:>{width}}" for v in row) for row in dist]


def main() -> None:
    if len(GRID) != ROWS or any(len(row) != COLS for row in GRID):
        raise ValueError(f"grid must be {ROWS}x{COLS}")

    if not any("#" in row for row in GRID):
        print("No marked cells; no distances to compute.")
        return

    dist = multi_source_bfs(GRID)
    print(f"Manhattan distance to nearest marked cell ({ROWS}x{COLS}):")
    for line in format_grid(dist):
        print(line)


if __name__ == "__main__":
    main()
