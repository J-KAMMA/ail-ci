# task: Recursively count the monotone lattice paths in a 6x6 grid from top-left to bottom-right using memoization.
"""Count monotone lattice paths across a 6x6 grid of cells.

A 6x6 grid of cells has 7x7 lattice points. A monotone path from the
top-left corner (0, 0) to the bottom-right corner (6, 6) moves only right
or down. The count is computed recursively with memoization and checked
against the closed form C(12, 6) = 924.
"""

from functools import lru_cache
from math import comb

GRID_CELLS: int = 6


@lru_cache(maxsize=None)
def count_paths(row: int, col: int) -> int:
    """Return the number of monotone paths from (row, col) to the bottom-right corner.

    The target is (GRID_CELLS, GRID_CELLS). Moves are only down (row + 1)
    or right (col + 1).
    """
    if row == GRID_CELLS and col == GRID_CELLS:
        return 1
    total: int = 0
    if row < GRID_CELLS:
        total += count_paths(row + 1, col)
    if col < GRID_CELLS:
        total += count_paths(row, col + 1)
    return total


def main() -> None:
    recursive_count: int = count_paths(0, 0)
    closed_form: int = comb(2 * GRID_CELLS, GRID_CELLS)
    print(f"Grid size: {GRID_CELLS}x{GRID_CELLS} cells "
          f"({GRID_CELLS + 1}x{GRID_CELLS + 1} lattice points)")
    print(f"Monotone paths (memoized recursion): {recursive_count}")
    print(f"Monotone paths (closed form C(12, 6)): {closed_form}")
    print(f"Results match: {recursive_count == closed_form}")


if __name__ == "__main__":
    main()
