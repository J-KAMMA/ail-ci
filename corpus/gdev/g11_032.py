# task: Convert a hard-coded 5x5 grid of integers into its prefix-sum table and answer a fixed set of rectangle sum queries, printing the answers.
from typing import List, Tuple


GRID: List[List[int]] = [
    [3, 1, 4, 1, 5],
    [9, 2, 6, 5, 3],
    [5, 8, 9, 7, 9],
    [3, 2, 3, 8, 4],
    [6, 2, 6, 4, 3],
]

# Each query is (r1, c1, r2, c2), inclusive corners, 0-based indices.
QUERIES: List[Tuple[int, int, int, int]] = [
    (0, 0, 0, 0),
    (0, 0, 4, 4),
    (1, 1, 3, 3),
    (2, 0, 4, 2),
    (0, 3, 1, 4),
    (3, 3, 3, 4),
    (4, 0, 4, 0),
    (1, 2, 2, 2),
]


def build_prefix_sums(grid: List[List[int]]) -> List[List[int]]:
    """Return a (rows+1) x (cols+1) prefix-sum table with a zero border."""
    rows = len(grid)
    cols = len(grid[0]) if rows else 0
    prefix: List[List[int]] = [[0] * (cols + 1) for _ in range(rows + 1)]
    for r in range(rows):
        for c in range(cols):
            prefix[r + 1][c + 1] = (
                grid[r][c]
                + prefix[r][c + 1]
                + prefix[r + 1][c]
                - prefix[r][c]
            )
    return prefix


def rect_sum(
    prefix: List[List[int]], r1: int, c1: int, r2: int, c2: int
) -> int:
    """Sum of the inclusive rectangle [r1..r2] x [c1..c2] using prefix sums."""
    return (
        prefix[r2 + 1][c2 + 1]
        - prefix[r1][c2 + 1]
        - prefix[r2 + 1][c1]
        + prefix[r1][c1]
    )


def brute_rect_sum(
    grid: List[List[int]], r1: int, c1: int, r2: int, c2: int
) -> int:
    """Direct summation, used to verify the prefix-sum answers."""
    return sum(grid[r][c] for r in range(r1, r2 + 1) for c in range(c1, c2 + 1))


def main() -> None:
    prefix = build_prefix_sums(GRID)

    print("Prefix-sum table:")
    for row in prefix:
        print(" ".join(f"{value:4d}" for value in row))
    print()

    print("Rectangle sum queries:")
    for index, (r1, c1, r2, c2) in enumerate(QUERIES, start=1):
        fast = rect_sum(prefix, r1, c1, r2, c2)
        slow = brute_rect_sum(GRID, r1, c1, r2, c2)
        status = "ok" if fast == slow else "MISMATCH"
        print(
            f"Query {index}: rows {r1}-{r2}, cols {c1}-{c2} -> {fast} [{status}]"
        )


if __name__ == "__main__":
    main()
