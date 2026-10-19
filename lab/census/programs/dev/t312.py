import sys


def main() -> None:
    data = sys.stdin.read().split()
    if not data:
        return
    idx = 0
    k = int(data[idx])
    idx += 1
    coins: list[int] = [int(data[idx + i]) for i in range(k)]
    idx += k
    target = int(data[idx]) if idx < len(data) else 0

    MOD = 1_000_000_007

    # Unordered combinations (exact, arbitrary precision).
    comb: list[int] = [0] * (target + 1)
    comb[0] = 1
    for c in coins:
        if c <= 0:
            continue
        for s in range(c, target + 1):
            comb[s] += comb[s - c]

    # Ordered ways (sequences), modulo 1000000007.
    ordered: list[int] = [0] * (target + 1)
    ordered[0] = 1
    for s in range(1, target + 1):
        total = 0
        for c in coins:
            if 0 < c <= s:
                total += ordered[s - c]
        ordered[s] = total % MOD

    print(comb[target], ordered[target])


if __name__ == "__main__":
    main()
