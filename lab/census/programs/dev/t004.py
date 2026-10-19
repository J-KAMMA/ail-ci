import sys
from collections import Counter


def main() -> None:
    data = sys.stdin.read().split()
    if not data:
        return
    n = int(data[0])
    values: list[int] = [int(x) for x in data[1:1 + n]]
    if not values:
        return
    counts = Counter(values)
    best_count = max(counts.values())
    mode = min(v for v, c in counts.items() if c == best_count)
    print(mode, best_count)


if __name__ == "__main__":
    main()
