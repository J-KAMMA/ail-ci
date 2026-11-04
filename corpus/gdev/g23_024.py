# task: Compute the rank of a hard-coded matrix using Gaussian elimination with fractions and print it.
from fractions import Fraction
from typing import List


MATRIX: List[List[int]] = [
    [1, 2, 3, 4],
    [2, 4, 6, 8],
    [1, 0, 1, 0],
    [3, 1, 4, 2],
    [0, 1, 1, 1],
]


def to_fraction_matrix(matrix: List[List[int]]) -> List[List[Fraction]]:
    return [[Fraction(value) for value in row] for row in matrix]


def matrix_rank(matrix: List[List[int]]) -> int:
    a: List[List[Fraction]] = to_fraction_matrix(matrix)
    rows: int = len(a)
    cols: int = len(a[0]) if rows else 0
    rank: int = 0
    pivot_row: int = 0

    for col in range(cols):
        if pivot_row >= rows:
            break

        pivot: int = pivot_row
        while pivot < rows and a[pivot][col] == 0:
            pivot += 1
        if pivot == rows:
            continue

        a[pivot_row], a[pivot] = a[pivot], a[pivot_row]

        pivot_value: Fraction = a[pivot_row][col]
        for r in range(pivot_row + 1, rows):
            if a[r][col] != 0:
                factor: Fraction = a[r][col] / pivot_value
                for c in range(col, cols):
                    a[r][c] -= factor * a[pivot_row][c]

        pivot_row += 1
        rank += 1

    return rank


def main() -> None:
    rank: int = matrix_rank(MATRIX)
    print(f"Rank: {rank}")


if __name__ == "__main__":
    main()
