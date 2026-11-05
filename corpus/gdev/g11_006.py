# task: Simulate heat diffusion on a 10x10 grid with fixed boundary temperatures using Jacobi iteration for 100 steps and print the center cell's temperature rounded to 3 decimals.
"""Simulate 2D heat diffusion on a 10x10 grid using Jacobi iteration.

The outer ring of cells is held at fixed temperatures (the boundary).
Interior cells start at 0 and are updated each step as the average of
their four neighbours, using only values from the previous step.
After 100 steps, the center cell's temperature is printed.
"""

from __future__ import annotations

GRID_SIZE: int = 10
NUM_STEPS: int = 100
TOP_TEMP: float = 100.0
OTHER_BOUNDARY_TEMP: float = 0.0
INTERIOR_START_TEMP: float = 0.0

Grid = list[list[float]]


def make_grid(size: int) -> Grid:
    """Create a grid with fixed boundary temperatures and an initialized interior."""
    grid: Grid = [[INTERIOR_START_TEMP] * size for _ in range(size)]
    for j in range(size):
        grid[0][j] = TOP_TEMP
        grid[size - 1][j] = OTHER_BOUNDARY_TEMP
    for i in range(size):
        grid[i][0] = OTHER_BOUNDARY_TEMP
        grid[i][size - 1] = OTHER_BOUNDARY_TEMP
    return grid


def jacobi_step(grid: Grid) -> Grid:
    """Return a new grid where each interior cell is the mean of its 4 neighbours.

    Boundary cells are copied unchanged, so they remain fixed.
    """
    size = len(grid)
    new_grid: Grid = [row[:] for row in grid]
    for i in range(1, size - 1):
        for j in range(1, size - 1):
            new_grid[i][j] = 0.25 * (
                grid[i - 1][j]
                + grid[i + 1][j]
                + grid[i][j - 1]
                + grid[i][j + 1]
            )
    return new_grid


def main() -> None:
    grid = make_grid(GRID_SIZE)
    for _ in range(NUM_STEPS):
        grid = jacobi_step(grid)

    # For an even-sized grid there is no single center cell; use the
    # index n // 2 in each dimension as the designated center.
    center_index = GRID_SIZE // 2
    center_temp = grid[center_index][center_index]
    print(f"{center_temp:.3f}")


if __name__ == "__main__":
    main()
