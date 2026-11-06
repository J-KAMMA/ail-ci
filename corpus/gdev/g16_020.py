# task: Compute the digit sum of 2**100 by consuming a generator that yields its decimal digits and print the total.
from typing import Iterator


def decimal_digits(n: int) -> Iterator[int]:
    """Yield the decimal digits of a non-negative integer, most significant first."""
    for ch in str(n):
        yield int(ch)


def digit_sum(digits: Iterator[int]) -> int:
    """Consume an iterator of digits and return their sum."""
    total = 0
    for d in digits:
        total += d
    return total


def main() -> None:
    value = 2 ** 100
    total = digit_sum(decimal_digits(value))
    print(total)


if __name__ == "__main__":
    main()
