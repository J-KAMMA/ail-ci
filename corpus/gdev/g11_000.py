# task: Simulate Conway's Game of Life on a 20x20 grid starting from a fixed glider pattern for 50 generations and print the final live cell count.
from __future__ import annotations

SIZE: int = 20
GENERATIONS: int = 50

Grid = list[list[int]]


def make_glider_grid(size: int) -> Grid:
    """Create an empty grid and place a glider near the top-left corner."""
    grid: Grid = [[0] * size for _ in range(size)]
    glider_cells: list[tuple[int, int]] = [
        (0, 1),
        (1, 2),
        (2, 0),
        (2, 1),
        (2, 2),
    ]
    offset_row, offset_col = 1, 1
    for r, c in glider_cells:
        grid[r + offset_row][c + offset_col] = 1
    return grid


def count_live_neighbors(grid: Grid, row: int, col: int) -> int:
    """Count live neighbors of a cell, using wrap-around (toroidal) edges."""
    size = len(grid)
    total = 0
    for dr in (-1, 0, 1):
        for dc in (-1, 0, 1):
            if dr == 0 and dc == 0:
                continue
            total += grid[(row + dr) % size][(col + dc) % size]
    return total


def step(grid: Grid) -> Grid:
    """Compute the next generation of Conway's Game of Life."""
    size = len(grid)
    new_grid: Grid = [[0] * size for _ in range(size)]
    for r in range(size):
        for c in range(size):
            neighbors = count_live_neighbors(grid, r, c)
            if grid[r][c] == 1:
                new_grid[r][c] = 1 if neighbors in (2, 3) else 0
            else:
                new_grid[r][c] = 1 if neighbors == 3 else 0
    return new_grid


def count_live_cells(grid: Grid) -> int:
    """Return the number of live cells in the grid."""
    return sum(sum(row) for row in grid)


def main() -> None:
    grid: Grid = make_glider_grid(SIZE)
    for _ in range(GENERATIONS):
        grid = step(grid)
    print(count_live_cells(grid))


if __name__ == "__main__":
    main()
