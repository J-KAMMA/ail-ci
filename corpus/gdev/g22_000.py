# task: Count the set bits in every integer from 0 to 1000 using Kernighan's algorithm and print the total.
from typing import Iterable


def count_set_bits(n: int) -> int:
    """Count set bits in a non-negative integer using Kernighan's algorithm."""
    count: int = 0
    while n:
        n &= n - 1  # clear the lowest set bit
        count += 1
    return count


def total_set_bits(values: Iterable[int]) -> int:
    """Sum the set-bit counts of all given integers."""
    return sum(count_set_bits(v) for v in values)


def main() -> None:
    total: int = total_set_bits(range(0, 1001))
    print(total)


if __name__ == "__main__":
    main()
