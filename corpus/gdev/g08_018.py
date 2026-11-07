# task: Recursively compute the determinant of a 4x4 integer matrix using Laplace (cofactor) expansion and print it.
from typing import List


Matrix = List[List[int]]


def minor(matrix: Matrix, row: int, col: int) -> Matrix:
    """Return the submatrix obtained by deleting the given row and column."""
    return [
        [value for j, value in enumerate(r) if j != col]
        for i, r in enumerate(matrix)
        if i != row
    ]


def determinant(matrix: Matrix) -> int:
    """Recursively compute the determinant using Laplace (cofactor) expansion
    along the first row."""
    n = len(matrix)
    if n == 0:
        return 1
    if n == 1:
        return matrix[0][0]
    if n == 2:
        return matrix[0][0] * matrix[1][1] - matrix[0][1] * matrix[1][0]

    total = 0
    for col in range(n):
        entry = matrix[0][col]
        if entry == 0:
            continue
        sign = 1 if col % 2 == 0 else -1
        total += sign * entry * determinant(minor(matrix, 0, col))
    return total


def main() -> None:
    matrix: Matrix = [
        [4, 3, 2, 1],
        [0, -1, 5, 2],
        [3, 7, -2, 6],
        [1, 0, 8, -3],
    ]

    for row in matrix:
        print(" ".join(f"{value:>4}" for value in row))

    result = determinant(matrix)
    print(f"Determinant: {result}")


if __name__ == "__main__":
    main()
