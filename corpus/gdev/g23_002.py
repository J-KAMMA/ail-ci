# task: Transpose a hard-coded non-square matrix represented as a list of lists and print the transposed rows.
from typing import List


def transpose(matrix: List[List[int]]) -> List[List[int]]:
    """Return the transpose of a (possibly non-square) matrix."""
    if not matrix:
        return []
    return [list(row) for row in zip(*matrix)]


def main() -> None:
    matrix: List[List[int]] = [
        [1, 2, 3, 4],
        [5, 6, 7, 8],
        [9, 10, 11, 12],
    ]

    print(f"Original shape: {len(matrix)} rows x {len(matrix[0])} columns")
    for row in matrix:
        print(row)

    transposed = transpose(matrix)

    print(f"Transposed shape: {len(transposed)} rows x {len(transposed[0])} columns")
    for row in transposed:
        print(row)


if __name__ == "__main__":
    main()
