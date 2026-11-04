# task: Count the unique paths through a hardcoded m×n grid containing obstacles, moving only right or down, and print the count.
from typing import List


GRID: List[List[int]] = [
    [0, 0, 0, 0, 0],
    [0, 1, 0, 0, 0],
    [0, 0, 0, 1, 0],
    [1, 0, 0, 0, 0],
    [0, 0, 1, 0, 0],
]


def count_unique_paths(grid: List[List[int]]) -> int:
    """Count right/down paths from top-left to bottom-right avoiding obstacles (1)."""
    if not grid or not grid[0]:
        return 0

    rows = len(grid)
    cols = len(grid[0])

    if grid[0][0] == 1 or grid[rows - 1][cols - 1] == 1:
        return 0

    ways: List[int] = [0] * cols
    ways[0] = 1

    for r in range(rows):
        for c in range(cols):
            if grid[r][c] == 1:
                ways[c] = 0
            elif c > 0:
                ways[c] += ways[c - 1]

    return ways[cols - 1]


def main() -> None:
    paths: int = count_unique_paths(GRID)
    print(f"Grid size: {len(GRID)}x{len(GRID[0])}")
    print(f"Unique paths: {paths}")


if __name__ == "__main__":
    main()
