import sys


def min_jumps(a: list[int]) -> int:
    """Return the minimum number of jumps from index 0 to the last index,
    or -1 if the last index is unreachable.

    From index i, one may jump to any index j with 1 <= j - i <= |a[i]|.
    A zero value blocks any further movement from that index.
    """
    n = len(a)
    if n <= 1:
        return 0

    jumps = 0
    end = 0       # furthest index reachable with the current number of jumps
    farthest = 0  # furthest index reachable with one more jump

    for i in range(n - 1):
        farthest = max(farthest, i + abs(a[i]))
        if i == end:
            if farthest <= i:
                return -1
            jumps += 1
            end = farthest
            if end >= n - 1:
                return jumps

    return -1


def main() -> None:
    data = sys.stdin.read().split()
    a = [int(tok) for tok in data]
    print(min_jumps(a))


if __name__ == "__main__":
    main()
