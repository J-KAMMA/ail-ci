# task: Find the side length of the largest square of 1s in a fixed binary matrix using DP and print it.
from typing import List


def largest_square_side(matrix: List[List[int]]) -> int:
    """Return the side length of the largest square consisting only of 1s.

    Uses the classic DP: dp[i][j] is the side of the largest all-ones square
    whose bottom-right corner is at (i, j).
    """
    if not matrix or not matrix[0]:
        return 0

    rows = len(matrix)
    cols = len(matrix[0])
    dp: List[List[int]] = [[0] * cols for _ in range(rows)]
    best = 0

    for i in range(rows):
        for j in range(cols):
            if matrix[i][j] == 1:
                if i == 0 or j == 0:
                    dp[i][j] = 1
                else:
                    dp[i][j] = 1 + min(dp[i - 1][j],
                                       dp[i][j - 1],
                                       dp[i - 1][j - 1])
                best = max(best, dp[i][j])

    return best


def main() -> None:
    matrix: List[List[int]] = [
        [1, 0, 1, 0, 0],
        [1, 0, 1, 1, 1],
        [1, 1, 1, 1, 1],
        [1, 0, 0, 1, 0],
        [1, 1, 1, 1, 1],
        [0, 1, 1, 1, 1],
    ]

    side = largest_square_side(matrix)
    print(f"Largest square of 1s has side length: {side}")


if __name__ == "__main__":
    main()
