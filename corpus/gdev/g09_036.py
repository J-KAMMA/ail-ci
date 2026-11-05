# task: Compute the minimum path sum from the top to the bottom of a fixed triangle of numbers, moving to adjacent entries below, and print it.
from typing import List


TRIANGLE: List[List[int]] = [
    [3],
    [7, 4],
    [2, 4, 6],
    [8, 5, 9, 3],
    [1, 6, 3, 7, 2],
    [9, 2, 8, 4, 6, 6],
]


def min_path_sum(triangle: List[List[int]]) -> int:
    """Return the minimum top-to-bottom path sum, moving to adjacent entries below."""
    if not triangle:
        return 0
    best: List[int] = list(triangle[-1])
    for row_index in range(len(triangle) - 2, -1, -1):
        row = triangle[row_index]
        best = [
            row[j] + min(best[j], best[j + 1])
            for j in range(len(row))
        ]
    return best[0]


def main() -> None:
    result = min_path_sum(TRIANGLE)
    print(f"Minimum path sum: {result}")


if __name__ == "__main__":
    main()
