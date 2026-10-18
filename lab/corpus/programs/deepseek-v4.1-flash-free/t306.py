import sys


def longest_common_subsequence(a: str, b: str) -> tuple[int, str]:
    n, m = len(a), len(b)
    dp = [[0] * (m + 1) for _ in range(n + 1)]
    for i in range(1, n + 1):
        prev = dp[i - 1]
        cur = dp[i]
        ai = a[i - 1]
        for j in range(1, m + 1):
            if ai == b[j - 1]:
                cur[j] = prev[j - 1] + 1
            else:
                cur[j] = prev[j] if prev[j] >= cur[j - 1] else cur[j - 1]

    length = dp[n][m]

    chars: list[str] = []
    i, j = n, m
    while i > 0 and j > 0:
        if a[i - 1] == b[j - 1]:
            chars.append(a[i - 1])
            i -= 1
            j -= 1
        elif dp[i - 1][j] >= dp[i][j - 1]:
            i -= 1
        else:
            j -= 1

    chars.reverse()
    return length, "".join(chars)


def main() -> None:
    data = sys.stdin.read().splitlines()
    a = data[0] if len(data) > 0 else ""
    b = data[1] if len(data) > 1 else ""
    length, subseq = longest_common_subsequence(a, b)
    print(length)
    print(subseq)


if __name__ == "__main__":
    main()
