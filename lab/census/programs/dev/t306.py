import sys


def main() -> None:
    data = sys.stdin.read().split("\n")
    a = data[0].strip() if len(data) > 0 else ""
    b = data[1].strip() if len(data) > 1 else ""

    n, m = len(a), len(b)

    # dp[i][j] = LCS length of a[i:] and b[j:]
    dp: list[list[int]] = [[0] * (m + 1) for _ in range(n + 1)]
    for i in range(n - 1, -1, -1):
        row = dp[i]
        next_row = dp[i + 1]
        ai = a[i]
        for j in range(m - 1, -1, -1):
            if ai == b[j]:
                row[j] = next_row[j + 1] + 1
            else:
                row[j] = max(next_row[j], row[j + 1])

    # Reconstruct one LCS by walking forward through the table.
    i = 0
    j = 0
    out: list[str] = []
    while i < n and j < m:
        if a[i] == b[j]:
            out.append(a[i])
            i += 1
            j += 1
        elif dp[i + 1][j] >= dp[i][j + 1]:
            i += 1
        else:
            j += 1

    print(len(out))
    print("".join(out))


if __name__ == "__main__":
    main()
