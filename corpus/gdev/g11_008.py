# task: Compute the sum of every 3x3 sub-grid of a fixed 6x6 matrix and print the 4x4 result of sums.
from typing import List


MATRIX: List[List[int]] = [
    [1, 2, 3, 4, 5, 6],
    [7, 8, 9, 10, 11, 12],
    [13, 14, 15, 16, 17, 18],
    [19, 20, 21, 22, 23, 24],
    [25, 26, 27, 28, 29, 30],
    [31, 32, 33, 34, 35, 36],
]

SUB_SIZE: int = 3


def sub_grid_sums(matrix: List[List[int]], size: int) -> List[List[int]]:
    """Return the sum of every size x size sub-grid of the matrix."""
    rows = len(matrix)
    cols = len(matrix[0]) if rows else 0
    result: List[List[int]] = []
    for r in range(rows - size + 1):
        row_sums: List[int] = []
        for c in range(cols - size + 1):
            total = 0
            for i in range(r, r + size):
                for j in range(c, c + size):
                    total += matrix[i][j]
            row_sums.append(total)
        result.append(row_sums)
    return result


def format_grid(grid: List[List[int]]) -> str:
    """Format a grid of integers as right-aligned columns."""
    width = max(len(str(value)) for row in grid for value in row)
    return "\n".join(
        " ".join(str(value).rjust(width) for value in row) for row in grid
    )


def main() -> None:
    sums = sub_grid_sums(MATRIX, SUB_SIZE)
    print(format_grid(sums))


if __name__ == "__main__":
    main()
