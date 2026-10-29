# task: Compute the number of trailing zeros of 1000! by counting factors of 5 and print it.
from __future__ import annotations


def count_trailing_zeros_factorial(n: int) -> int:
    """Return the number of trailing zeros in n! by counting factors of 5."""
    count = 0
    power = 5
    while power <= n:
        count += n // power
        power *= 5
    return count


def main() -> None:
    n: int = 1000
    print(count_trailing_zeros_factorial(n))


if __name__ == "__main__":
    main()
