# task: Compute the minimum number of insertions needed to turn a fixed string into a palindrome and print it.
def min_insertions(s: str) -> int:
    """Return the minimum number of characters to insert into s to make it a palindrome."""
    n: int = len(s)
    if n < 2:
        return 0

    # dp[i][j] = minimum insertions to make the substring s[i..j] a palindrome
    dp: list[list[int]] = [[0] * n for _ in range(n)]

    for length in range(2, n + 1):
        for i in range(n - length + 1):
            j: int = i + length - 1
            if s[i] == s[j]:
                # Inner substring is s[i+1..j-1]; for length 2 there is no inner part.
                dp[i][j] = dp[i + 1][j - 1] if length > 2 else 0
            else:
                dp[i][j] = 1 + min(dp[i + 1][j], dp[i][j - 1])

    return dp[0][n - 1]


def main() -> None:
    text: str = "leetcode"
    result: int = min_insertions(text)
    print(f"String: {text}")
    print(f"Minimum insertions to make a palindrome: {result}")


if __name__ == "__main__":
    main()
