# task: Find the minimum number of deletions needed to make a fixed string a palindrome and print it.
def min_deletions_for_palindrome(s: str) -> int:
    """Return the minimum number of deletions needed to make s a palindrome.

    This equals len(s) minus the length of the longest palindromic
    subsequence, computed with an O(n^2) interval dynamic program.
    """
    n: int = len(s)
    if n == 0:
        return 0

    # dp[i][j] = length of the longest palindromic subsequence of s[i..j]
    dp: list[list[int]] = [[0] * n for _ in range(n)]
    for i in range(n):
        dp[i][i] = 1

    for length in range(2, n + 1):
        for i in range(n - length + 1):
            j: int = i + length - 1
            if s[i] == s[j]:
                inner: int = dp[i + 1][j - 1] if i + 1 <= j - 1 else 0
                dp[i][j] = inner + 2
            else:
                dp[i][j] = max(dp[i + 1][j], dp[i][j - 1])

    return n - dp[0][n - 1]


def main() -> None:
    text: str = "geeksforgeeks"
    print(min_deletions_for_palindrome(text))


if __name__ == "__main__":
    main()
