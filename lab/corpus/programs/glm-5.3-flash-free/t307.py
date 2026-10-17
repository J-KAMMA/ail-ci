import sys


def edit_counts(s: str, t: str) -> tuple[int, int, int]:
    """Return (insertions, deletions, substitutions) for one optimal
    edit-distance alignment transforming s into t."""
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

    ins = del_cnt = sub = 0
    i, j = n, m
    while i > 0 or j > 0:
        if i > 0 and j > 0:
            cost = 0 if s[i - 1] == t[j - 1] else 1
            if dp[i][j] == dp[i - 1][j - 1] + cost:
                if cost:
                    sub += 1
                i -= 1
                j -= 1
                continue
        if i > 0 and dp[i][j] == dp[i - 1][j] + 1:
            del_cnt += 1
            i -= 1
            continue
        ins += 1
        j -= 1
    return ins, del_cnt, sub


def main() -> None:
    lines = sys.stdin.read().splitlines()
    s = lines[0].strip() if len(lines) > 0 else ""
    t = lines[1].strip() if len(lines) > 1 else ""
    ins, del_cnt, sub = edit_counts(s, t)
    print(f"{ins} {del_cnt} {sub}")


if __name__ == "__main__":
    main()
