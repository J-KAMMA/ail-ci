import sys
from bisect import bisect_left


MOD = 1_000_000_007


def main() -> None:
    data = sys.stdin.read().split()
    a = [int(tok) for tok in data]
    n = len(a)

    # Prefix sums: P[0] = 0, P[i] = a[0] + ... + a[i-1]
    prefix: list[int] = [0] * (n + 1)
    for i in range(1, n + 1):
        prefix[i] = prefix[i - 1] + a[i - 1]

    # Coordinate compression of prefix sums
    values = sorted(set(prefix))
    m = len(values)

    def rank(x: int) -> int:
        # 1-indexed rank for Fenwick tree
        return bisect_left(values, x) + 1

    tree: list[int] = [0] * (m + 1)

    def add(pos: int, val: int) -> None:
        while pos <= m:
            tree[pos] = (tree[pos] + val) % MOD
            pos += pos & (-pos)

    def query(pos: int) -> int:
        total = 0
        while pos > 0:
            total += tree[pos]
            pos -= pos & (-pos)
        return total % MOD

    # dp[i] = number of valid splits of the first i elements
    # dp[i] = sum of dp[j] for j < i with P[j] <= P[i]
    dp0 = 1
    add(rank(prefix[0]), dp0)
    dp_last = dp0
    for i in range(1, n + 1):
        r = rank(prefix[i])
        dp_i = query(r) % MOD
        add(r, dp_i)
        dp_last = dp_i

    if n == 0:
        print(1)
    else:
        print(dp_last % MOD)


if __name__ == "__main__":
    main()
