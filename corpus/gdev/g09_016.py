# task: Compute the partition number p(100), the number of ways to write 100 as a sum of positive integers regardless of order, and print it.
from typing import List


def partition_count(n: int) -> int:
    """Return the number of partitions of n using dynamic programming."""
    ways: List[int] = [1] + [0] * n
    for part in range(1, n + 1):
        for total in range(part, n + 1):
            ways[total] += ways[total - part]
    return ways[n]


def main() -> None:
    print(partition_count(100))


if __name__ == "__main__":
    main()
