import sys
from collections import Counter


def main() -> None:
    data = sys.stdin.read().split()
    if not data:
        print(0)
        return
    n = int(data[0])
    values = data[1:1 + n]
    counts = Counter(int(x) for x in values)
    total = sum(c * (c - 1) // 2 for c in counts.values())
    print(total)


if __name__ == "__main__":
    main()
