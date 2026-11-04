# task: Count the partitions of 200 into distinct parts using dynamic programming and print the result.
from typing import List


def count_distinct_partitions(n: int) -> int:
    """Return the number of partitions of n into distinct parts."""
    ways: List[int] = [0] * (n + 1)
    ways[0] = 1
    for part in range(1, n + 1):
        for total in range(n, part - 1, -1):
            ways[total] += ways[total - part]
    return ways[n]


def main() -> None:
    n: int = 200
    result: int = count_distinct_partitions(n)
    print(f"Number of partitions of {n} into distinct parts: {result}")


if __name__ == "__main__":
    main()
