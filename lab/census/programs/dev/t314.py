import bisect
import sys


def non_decreasing_ending_lengths(seq: list[int]) -> list[int]:
    """Return, for each index i, the length of the longest non-decreasing
    subsequence that ends at element i."""
    tails: list[int] = []
    result: list[int] = []
    for x in seq:
        pos = bisect.bisect_right(tails, x)
        if pos == len(tails):
            tails.append(x)
        else:
            tails[pos] = x
        result.append(pos + 1)
    return result


def main() -> None:
    data = sys.stdin.read().split()
    values = [int(tok) for tok in data]

    if not values:
        print(0)
        print(0)
        return

    # Longest non-decreasing subsequence (LNDS).
    inc = non_decreasing_ending_lengths(values)
    lnds = max(inc)

    # Longest bitonic subsequence: non-decreasing then non-increasing.
    # dec[i] = longest non-increasing subsequence starting at i (going right).
    # Reversing the array turns this into a non-decreasing subsequence ending at i.
    rev_lengths = non_decreasing_ending_lengths(values[::-1])
    dec = rev_lengths[::-1]

    bitonic = max(inc[i] + dec[i] - 1 for i in range(len(values)))

    print(lnds)
    print(bitonic)


if __name__ == "__main__":
    main()
