import sys


def edit_alignment_counts(s: str, t: str) -> tuple[int, int, int]:
    n, m = len(s), len(t)

    dp = [[0] * (m + 1) for _ in range(n + 1)]
    for i in range(n + 1):
        dp[i][0] = i
    for j in range(m + 1):
        dp[0][j] = j

    for i in range(1, n + 1):
        for j in range(1, m + 1):
            cost = 0 if s[i - 1] == t[j - 1] else 1
            dp[i][j] = min(
                dp[i - 1][j] + 1,
                dp[i][j - 1] + 1,
                dp[i - 1][j - 1] + cost,
            )

    ins = dele = sub = 0
    i, j = n, m
    while i > 0 or j > 0:
        cost = 0 if s[i - 1] == t[j - 1] else 1 if i > 0 and j > 0 else None
        if i > 0 and j > 0 and dp[i][j] == dp[i - 1][j - 1] + cost:
            if cost == 1:
                sub += 1
            i -= 1
            j -= 1
        elif i > 0 and dp[i][j] == dp[i - 1][j] + 1:
            dele += 1
            i -= 1
        else:
            ins += 1
            j -= 1

    return ins, dele, sub


def main() -> None:
    lines = sys.stdin.read().splitlines()
    s = lines[0] if len(lines) > 0 else ""
    t = lines[1] if len(lines) > 1 else ""
    ins, dele, sub = edit_alignment_counts(s, t)
    print(f"{ins} {dele} {sub}")


if __name__ == "__main__":
    main()
