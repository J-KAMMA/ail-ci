import sys
from bisect import bisect_left

MOD = 1_000_000_007


def main() -> None:
    tokens = sys.stdin.buffer.read().split()
    n = len(tokens)
    if n == 0:
        print(0)
        return
    a = list(map(int, tokens))

    prefix = [0] * (n + 1)
    for i in range(1, n + 1):
        prefix[i] = prefix[i - 1] + a[i - 1]

    sorted_vals = sorted(set(prefix))
    m = len(sorted_vals)
    tree = [0] * (m + 1)

    def update(pos: int, value: int) -> None:
        while pos <= m:
            tree[pos] = (tree[pos] + value) % MOD
            pos += pos & (-pos)

    def query(pos: int) -> int:
        total = 0
        while pos > 0:
            total = (total + tree[pos]) % MOD
            pos -= pos & (-pos)
        return total

    update(1, 1)

    result = 0
    for i in range(1, n + 1):
        rank = bisect_left(sorted_vals, prefix[i]) + 1
        result = query(rank)
        update(rank, result)

    print(result % MOD)


if __name__ == "__main__":
    main()
