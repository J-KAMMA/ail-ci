# task: Find the maximum and minimum element and their positions in a hard-coded matrix and print them.
from typing import List, Tuple

MATRIX: List[List[int]] = [
    [14, 3, 27, 8],
    [-5, 19, 0, 42],
    [11, 6, -17, 23],
]


def find_extremes(matrix: List[List[int]]) -> Tuple[int, Tuple[int, int], int, Tuple[int, int]]:
    """Return (max_value, (row, col) of first max, min_value, (row, col) of first min)."""
    max_val = matrix[0][0]
    max_pos = (0, 0)
    min_val = matrix[0][0]
    min_pos = (0, 0)

    for r, row in enumerate(matrix):
        for c, value in enumerate(row):
            if value > max_val:
                max_val = value
                max_pos = (r, c)
            if value < min_val:
                min_val = value
                min_pos = (r, c)

    return max_val, max_pos, min_val, min_pos


def main() -> None:
    if not MATRIX or not MATRIX[0]:
        print("The matrix is empty.")
        return

    max_val, max_pos, min_val, min_pos = find_extremes(MATRIX)

    print(f"Matrix dimensions: {len(MATRIX)} rows x {len(MATRIX[0])} columns")
    print(f"Maximum element: {max_val} at row {max_pos[0]}, column {max_pos[1]}")
    print(f"Minimum element: {min_val} at row {min_pos[0]}, column {min_pos[1]}")


if __name__ == "__main__":
    main()
