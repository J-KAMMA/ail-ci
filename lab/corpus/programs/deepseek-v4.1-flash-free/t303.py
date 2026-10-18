import sys


def main() -> None:
    data = sys.stdin.read().split()
    if not data:
        return
    idx = 0
    n = int(data[idx]); idx += 1
    capacity = int(data[idx]); idx += 1

    weights = [0] * n
    values = [0] * n
    for i in range(n):
        weights[i] = int(data[idx]); idx += 1
        values[i] = int(data[idx]); idx += 1

    dp = [[0] * (capacity + 1) for _ in range(n + 1)]
    for i in range(1, n + 1):
        wi = weights[i - 1]
        vi = values[i - 1]
        row = dp[i]
        prev = dp[i - 1]
        for w in range(capacity + 1):
            best = prev[w]
            if wi <= w:
                cand = prev[w - wi] + vi
                if cand > best:
                    best = cand
            row[w] = best

    chosen = []
    w = capacity
    for i in range(n, 0, -1):
        if dp[i][w] != dp[i - 1][w]:
            chosen.append(i - 1)
            w -= weights[i - 1]
    chosen.reverse()

    out = [str(dp[n][capacity]), " ".join(map(str, chosen))]
    sys.stdout.write("\n".join(out) + "\n")


if __name__ == "__main__":
    main()
