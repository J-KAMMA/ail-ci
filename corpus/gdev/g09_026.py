# task: Compute the Stirling numbers of the second kind S(10, k) for all k using a DP recurrence and print the row.
from typing import List


def stirling2_row(n: int) -> List[int]:
    """Return [S(n, 0), S(n, 1), ..., S(n, n)] using the DP recurrence
    S(i, k) = k * S(i-1, k) + S(i-1, k-1), with S(0, 0) = 1."""
    prev: List[int] = [1]  # row for i = 0
    for i in range(1, n + 1):
        curr: List[int] = [0] * (i + 1)
        for k in range(1, i + 1):
            below = prev[k] if k < len(prev) else 0
            curr[k] = k * below + prev[k - 1]
        prev = curr
    return prev


def main() -> None:
    n: int = 10
    row: List[int] = stirling2_row(n)
    print(f"Stirling numbers of the second kind S({n}, k):")
    for k, value in enumerate(row):
        print(f"S({n}, {k}) = {value}")
    print("Row:", row)


if __name__ == "__main__":
    main()
