import sys


def main() -> None:
    data = sys.stdin.read().split()
    if not data:
        return
    n = int(data[0])
    values = data[1:1 + n]

    counts: dict[str, int] = {}
    for v in values:
        counts[v] = counts.get(v, 0) + 1

    total = sum(c * (c - 1) // 2 for c in counts.values())
    print(total)


if __name__ == "__main__":
    main()
