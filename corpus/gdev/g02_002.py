# task: Find all perfect numbers below 10,000 by summing proper divisors and print them.
from typing import Iterator


def proper_divisor_sum(n: int) -> int:
    """Return the sum of proper divisors of n (divisors less than n)."""
    if n < 2:
        return 0
    total = 1  # 1 is a proper divisor of every n > 1
    i = 2
    while i * i <= n:
        if n % i == 0:
            total += i
            other = n // i
            if other != i:
                total += other
        i += 1
    return total


def perfect_numbers(limit: int) -> Iterator[int]:
    """Yield all perfect numbers n with 1 <= n < limit, in ascending order."""
    for n in range(2, limit):
        if proper_divisor_sum(n) == n:
            yield n


def main() -> None:
    limit = 10_000
    found = list(perfect_numbers(limit))
    print(f"Perfect numbers below {limit:,}:")
    for number in found:
        print(number)
    print(f"Total: {len(found)}")


if __name__ == "__main__":
    main()
