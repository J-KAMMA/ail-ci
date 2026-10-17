import sys
from itertools import combinations


def main() -> None:
    n = int(sys.stdin.readline().strip())
    k = min(n, 5)
    elements = range(1, k + 1)

    out = []
    for size in range(k + 1):
        for subset in combinations(elements, size):
            out.append(" ".join(map(str, subset)))

    sys.stdout.write("\n".join(out))
    if out:
        sys.stdout.write("\n")


if __name__ == "__main__":
    main()
