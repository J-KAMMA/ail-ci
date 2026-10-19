import itertools
import sys


def main() -> None:
    line: str = sys.stdin.readline().strip()
    n: int = int(line)
    m: int = min(n, 6)

    count: int = 0
    last: tuple[int, ...] = ()
    derangements: int = 0

    # itertools.permutations yields tuples in lexicographic order for sorted input.
    for perm in itertools.permutations(range(1, m + 1)):
        count += 1
        last = perm
        if all(perm[i] != i + 1 for i in range(m)):
            derangements += 1

    print(count)
    print(" ".join(str(x) for x in last))
    print(derangements)


if __name__ == "__main__":
    main()
