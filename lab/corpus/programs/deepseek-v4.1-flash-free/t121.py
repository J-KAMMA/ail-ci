import sys
from collections import Counter


def main() -> None:
    data = sys.stdin.read().split()
    if not data:
        return
    n = int(data[0])
    names = data[1::2][:n]
    scores = [int(s) for s in data[2::2][:n]]

    best = max(scores)
    winner = names[scores.index(best)]

    counts = Counter(names)
    singles = [name for name in names if counts[name] == 1]

    print(winner)
    for name in singles:
        print(name)


if __name__ == "__main__":
    main()
