# task: Find the length of the longest common subsequence of two hardcoded strings using a DP table and print it.
from typing import List


def lcs_length(a: str, b: str) -> int:
    """Return the length of the longest common subsequence of a and b
    using a bottom-up dynamic programming table."""
    m: int = len(a)
    n: int = len(b)
    # dp[i][j] = LCS length of a[:i] and b[:j]
    dp: List[List[int]] = [[0] * (n + 1) for _ in range(m + 1)]
    for i in range(1, m + 1):
        for j in range(1, n + 1):
            if a[i - 1] == b[j - 1]:
                dp[i][j] = dp[i - 1][j - 1] + 1
            else:
                dp[i][j] = max(dp[i - 1][j], dp[i][j - 1])
    return dp[m][n]


def main() -> None:
    first: str = "AGGTABQWERTYXYZ"
    second: str = "GXTXAYBWRTZQXY"
    length: int = lcs_length(first, second)
    print(f"First string:  {first}")
    print(f"Second string: {second}")
    print(f"Length of longest common subsequence: {length}")


if __name__ == "__main__":
    main()
