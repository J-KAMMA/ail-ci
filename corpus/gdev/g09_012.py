# task: Count the number of palindromic substrings in a fixed string using a DP table and print the count.
from typing import List


def count_palindromic_substrings(s: str) -> int:
    """Count palindromic substrings of s using a DP table.

    dp[i][j] is True when s[i..j] (inclusive) is a palindrome.
    """
    n: int = len(s)
    if n == 0:
        return 0

    dp: List[List[bool]] = [[False] * n for _ in range(n)]
    count: int = 0

    # Iterate by substring length so that inner substrings are always ready.
    for length in range(1, n + 1):
        for i in range(0, n - length + 1):
            j: int = i + length - 1
            if s[i] == s[j] and (length <= 2 or dp[i + 1][j - 1]):
                dp[i][j] = True
                count += 1

    return count


def main() -> None:
    text: str = "abaxyzzyxf"
    result: int = count_palindromic_substrings(text)
    print(f"String: {text}")
    print(f"Number of palindromic substrings: {result}")


if __name__ == "__main__":
    main()
