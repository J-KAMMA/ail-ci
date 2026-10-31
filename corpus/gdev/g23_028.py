# task: Rotate a hard-coded square matrix 90 degrees clockwise and print the resulting matrix.
from typing import List


def rotate_clockwise(matrix: List[List[int]]) -> List[List[int]]:
    """Return a new matrix rotated 90 degrees clockwise."""
    # Reverse the rows, then transpose: row i of result is column i read bottom-to-top.
    return [list(row) for row in zip(*matrix[::-1])]


def format_matrix(matrix: List[List[int]]) -> str:
    """Format a matrix as aligned rows of numbers."""
    if not matrix:
        return ""
    width = max(len(str(value)) for row in matrix for value in row)
    return "\n".join(
        " ".join(str(value).rjust(width) for value in row) for row in matrix
    )


def main() -> None:
    matrix: List[List[int]] = [
        [1, 2, 3, 4],
        [5, 6, 7, 8],
        [9, 10, 11, 12],
        [13, 14, 15, 16],
    ]
    rotated = rotate_clockwise(matrix)
    print(format_matrix(rotated))


if __name__ == "__main__":
    main()
