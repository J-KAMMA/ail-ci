import sys
from collections import Counter


def main() -> None:
    tokens: list[str] = sys.stdin.read().split()
    nums: list[int] = [int(tok) for tok in tokens]

    # Top-3 distinct maximum values, largest first.
    distinct_sorted: list[int] = sorted(set(nums), reverse=True)
    top3: list[int] = distinct_sorted[:3]

    # Numbers that appear more than once, in ascending order.
    counts: Counter[int] = Counter(nums)
    repeated: list[int] = sorted(n for n, c in counts.items() if c > 1)

    print(" ".join(str(n) for n in top3))
    print(" ".join(str(n) for n in repeated))


if __name__ == "__main__":
    main()
