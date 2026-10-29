# task: Rotate a fixed 5x5 integer matrix 90 degrees clockwise and print the result row by row.
from typing import List


def rotate_clockwise(matrix: List[List[int]]) -> List[List[int]]:
    """Return a new matrix rotated 90 degrees clockwise."""
    rows = len(matrix)
    cols = len(matrix[0]) if rows else 0
    return [[matrix[rows - 1 - r][c] for r in range(rows)] for c in range(cols)]


def main() -> None:
    matrix: List[List[int]] = [
        [1, 2, 3, 4, 5],
        [6, 7, 8, 9, 10],
        [11, 12, 13, 14, 15],
        [16, 17, 18, 19, 20],
        [21, 22, 23, 24, 25],
    ]
    rotated = rotate_clockwise(matrix)
    for row in rotated:
        print(" ".join(str(value) for value in row))


if __name__ == "__main__":
    main()
