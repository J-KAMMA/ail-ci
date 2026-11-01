# task: Count the number of distinct ways to move from the top-left to the bottom-right of a 6x6 grid using only right and down moves while avoiding fixed obstacle cells, and print the count.
from typing import Final

GRID_SIZE: Final[int] = 6
OBSTACLES: Final[frozenset[tuple[int, int]]] = frozenset(
    {
        (1, 1),
        (1, 4),
        (2, 2),
        (3, 0),
        (3, 4),
        (4, 2),
    }
)


def count_paths(size: int, blocked: frozenset[tuple[int, int]]) -> int:
    """Count right/down paths from top-left to bottom-right avoiding blocked cells."""
    ways: list[list[int]] = [[0] * size for _ in range(size)]
    for row in range(size):
        for col in range(size):
            if (row, col) in blocked:
                ways[row][col] = 0
            elif row == 0 and col == 0:
                ways[row][col] = 1
            else:
                from_above = ways[row - 1][col] if row > 0 else 0
                from_left = ways[row][col - 1] if col > 0 else 0
                ways[row][col] = from_above + from_left
    return ways[size - 1][size - 1]


def main() -> None:
    total: int = count_paths(GRID_SIZE, OBSTACLES)
    print(total)


if __name__ == "__main__":
    main()
