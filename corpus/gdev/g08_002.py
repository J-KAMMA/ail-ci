# task: Use backtracking to count all solutions to the 8-queens problem and print the total.
from typing import Set


def solve(row: int, n: int, cols: Set[int], diag1: Set[int], diag2: Set[int]) -> int:
    """Count solutions by placing one queen per row using backtracking."""
    if row == n:
        return 1
    count = 0
    for col in range(n):
        d1 = row - col
        d2 = row + col
        if col in cols or d1 in diag1 or d2 in diag2:
            continue
        cols.add(col)
        diag1.add(d1)
        diag2.add(d2)
        count += solve(row + 1, n, cols, diag1, diag2)
        cols.remove(col)
        diag1.remove(d1)
        diag2.remove(d2)
    return count


def count_n_queens(n: int) -> int:
    return solve(0, n, set(), set(), set())


def main() -> None:
    total = count_n_queens(8)
    print(f"Total solutions to the 8-queens problem: {total}")


if __name__ == "__main__":
    main()
