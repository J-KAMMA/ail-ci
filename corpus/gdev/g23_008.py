# task: Check whether a hard-coded 3x3 matrix is symmetric and print True or False.
from typing import Sequence


def is_symmetric(matrix: Sequence[Sequence[int]]) -> bool:
    """Return True if a square matrix equals its transpose."""
    n = len(matrix)
    if any(len(row) != n for row in matrix):
        return False
    return all(matrix[i][j] == matrix[j][i] for i in range(n) for j in range(n))


def main() -> None:
    matrix: list[list[int]] = [
        [1, 2, 3],
        [2, 5, 6],
        [3, 6, 9],
    ]
    print(is_symmetric(matrix))


if __name__ == "__main__":
    main()
