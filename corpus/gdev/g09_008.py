# task: Find the length of the longest strictly increasing subsequence of a fixed integer sequence and print it.
import bisect
from typing import Sequence


def longest_strictly_increasing_length(seq: Sequence[int]) -> int:
    """Return the length of the longest strictly increasing subsequence.

    Uses patience sorting: tails[k] holds the smallest possible tail value
    of an increasing subsequence of length k + 1. bisect_left finds the
    first position where a value can be placed while keeping the sequence
    strictly increasing.
    """
    tails: list[int] = []
    for value in seq:
        pos = bisect.bisect_left(tails, value)
        if pos == len(tails):
            tails.append(value)
        else:
            tails[pos] = value
    return len(tails)


def main() -> None:
    # Fixed, deterministic input sequence.
    sequence: list[int] = [
        10, 9, 2, 5, 3, 7, 101, 18, 4, 4, 6, 8, -1, 0, 12, 11, 13, 1, 15, 14,
    ]
    result = longest_strictly_increasing_length(sequence)
    print(result)


if __name__ == "__main__":
    main()
