# task: Count the trailing zeros of integers 1 through 50 with a bit-scanning loop and print the results.
from __future__ import annotations


def count_trailing_zeros(n: int) -> int:
    """Count trailing zero bits of a positive integer using a bit-scanning loop."""
    if n <= 0:
        raise ValueError("n must be a positive integer")
    count = 0
    while (n & 1) == 0:
        n >>= 1
        count += 1
    return count


def main() -> None:
    for i in range(1, 51):
        print(f"{i}: {count_trailing_zeros(i)}")


if __name__ == "__main__":
    main()
