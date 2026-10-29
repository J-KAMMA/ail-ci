# task: Compute the determinant of a hard-coded 4x4 matrix recursively using Laplace expansion and print it.
from typing import Sequence


Matrix = Sequence[Sequence[float]]


def minor(matrix: Matrix, row: int, col: int) -> list[list[float]]:
    """Return the matrix with the given row and column removed."""
    return [
        [value for j, value in enumerate(r) if j != col]
        for i, r in enumerate(matrix)
        if i != row
    ]


def determinant(matrix: Matrix) -> float:
    """Compute the determinant recursively via Laplace (cofactor) expansion
    along the first row."""
    n = len(matrix)
    if n == 1:
        return matrix[0][0]
    if n == 2:
        return matrix[0][0] * matrix[1][1] - matrix[0][1] * matrix[1][0]
    total: float = 0
    for col in range(n):
        sign = 1 if col % 2 == 0 else -1
        total += sign * matrix[0][col] * determinant(minor(matrix, 0, col))
    return total


def main() -> None:
    matrix: list[list[float]] = [
        [4, 3, 2, 1],
        [0, 5, 1, 2],
        [3, 0, 6, 1],
        [1, 2, 0, 7],
    ]
    print(f"Matrix: {matrix}")
    result = determinant(matrix)
    print(f"Determinant: {result}")


if __name__ == "__main__":
    main()
