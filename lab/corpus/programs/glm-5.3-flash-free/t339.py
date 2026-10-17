import sys
from itertools import combinations


def main() -> None:
    n = int(sys.stdin.readline())
    m = min(n, 5)
    for r in range(m + 1):
        for combo in combinations(range(1, m + 1), r):
            print(" ".join(map(str, combo)))


if __name__ == "__main__":
    main()
