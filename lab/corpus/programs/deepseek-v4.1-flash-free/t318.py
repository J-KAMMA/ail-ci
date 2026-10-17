import sys
from typing import List


def main() -> None:
    data = sys.stdin.read().split()
    a: List[int] = list(map(int, data))
    n = len(a)
    MOD = 1000000007

    if n == 0:
        print(0)
        return

    prefix: List[int] = [0] * (n + 1)
    for i, x in enumerate(a):
        prefix[i + 1] = prefix[i] + x

    vals = sorted(set(prefix))
    index = {v: i + 1 for i, v in enumerate(vals)}
    m = len(vals)

    tree: List[int] = [0] * (m + 1)

    def update(i: int, val: int) -> None:
        while i <= m:
            tree[i] = (tree[i] + val) % MOD
            i += i & -i

    def query(i: int) -> int:
        s = 0
        while i > 0:
            s += tree[i]
            i -= i & -i
        return s % MOD

    dp: List[int] = [0] * (n + 1)
    dp[0] = 1
    update(index[prefix[0]], 1)

    for j in range(1, n + 1):
        dp[j] = query(index[prefix[j]])
        update(index[prefix[j]], dp[j])

    print(dp[n] % MOD)


if __name__ == "__main__":
    main()
