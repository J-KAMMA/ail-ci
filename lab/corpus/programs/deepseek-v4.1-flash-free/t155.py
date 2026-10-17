import sys
from collections import Counter


def main() -> None:
    data = sys.stdin.read().split()
    counts = Counter(int(x) for x in data)
    for value, count in sorted(counts.items(), key=lambda kv: (-kv[1], kv[0])):
        print(f"{value} {count}")


if __name__ == "__main__":
    main()
