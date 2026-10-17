import sys
from itertools import permutations


def derangements(m: int) -> int:
    if m == 0:
        return 1
    if m == 1:
        return 0
    prev2, prev1 = 1, 0
    for k in range(2, m + 1):
        prev2, prev1 = prev1, (k - 1) * (prev1 + prev2)
    return prev1


def main() -> None:
    data = sys.stdin.read().split()
    n = int(data[0])
    m = min(n, 6)

    count = 0
    last: tuple[int, ...] = ()
    for perm in permutations(range(1, m + 1)):
        count += 1
        last = perm

    print(count)
    print(" ".join(map(str, last)))
    print(derangements(m))


if __name__ == "__main__":
    main()
