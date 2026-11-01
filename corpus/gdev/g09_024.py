# task: Find the length of the longest bitonic subsequence of a fixed integer list and print it.
from typing import List


def longest_increasing_ending_at(values: List[int]) -> List[int]:
    """Length of the longest strictly increasing subsequence ending at each index."""
    n: int = len(values)
    lengths: List[int] = [1] * n
    for i in range(n):
        for j in range(i):
            if values[j] < values[i] and lengths[j] + 1 > lengths[i]:
                lengths[i] = lengths[j] + 1
    return lengths


def longest_decreasing_starting_at(values: List[int]) -> List[int]:
    """Length of the longest strictly decreasing subsequence starting at each index."""
    n: int = len(values)
    lengths: List[int] = [1] * n
    for i in range(n - 1, -1, -1):
        for j in range(i + 1, n):
            if values[j] < values[i] and lengths[j] + 1 > lengths[i]:
                lengths[i] = lengths[j] + 1
    return lengths


def longest_bitonic_length(values: List[int]) -> int:
    """Length of the longest subsequence that strictly increases then strictly decreases."""
    if not values:
        return 0
    inc: List[int] = longest_increasing_ending_at(values)
    dec: List[int] = longest_decreasing_starting_at(values)
    return max(i + d - 1 for i, d in zip(inc, dec))


def main() -> None:
    sequence: List[int] = [1, 11, 2, 10, 4, 5, 2, 1, 7, 3, 8, 6]
    result: int = longest_bitonic_length(sequence)
    print(f"Sequence: {sequence}")
    print(f"Length of longest bitonic subsequence: {result}")


if __name__ == "__main__":
    main()
