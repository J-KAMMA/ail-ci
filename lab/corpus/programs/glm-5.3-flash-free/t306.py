import sys


def longest_common_subsequence(s: str, t: str) -> str:
    """Return one longest common subsequence of s and t."""
    n, m = len(s), len(t)
    # dp[i][j] = length of the LCS of s[:i] and t[:j]
    dp = [[0] * (m + 1) for _ in range(n + 1)]
    for i in range(1, n + 1):
        for j in range(1, m + 1):
            if s[i - 1] == t[j - 1]:
                dp[i][j] = dp[i - 1][j - 1] + 1
            else:
                dp[i][j] = max(dp[i - 1][j], dp[i][j - 1])

    chars: list[str] = []
    i, j = n, m
    while i > 0 and j > 0:
        if s[i - 1] == t[j - 1]:
            chars.append(s[i - 1])
            i -= 1
            j -= 1
        elif dp[i - 1][j] >= dp[i][j - 1]:
            i -= 1
        else:
            j -= 1
    return "".join(reversed(chars))


def main() -> None:
    lines = sys.stdin.read().splitlines()
    s = lines[0].strip() if lines else ""
    t = lines[1].strip() if len(lines) > 1 else ""
    print(longest_common_subsequence(s, t))


if __name__ == "__main__":
    main()
