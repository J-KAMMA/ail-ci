# task: Find all Armstrong (narcissistic) numbers below 100,000 and print them.
from typing import List


def is_armstrong(n: int) -> bool:
    """Return True if n equals the sum of its digits each raised to the power of the digit count."""
    digits: List[int] = [int(d) for d in str(n)]
    power: int = len(digits)
    return sum(d ** power for d in digits) == n


def find_armstrong_numbers(limit: int) -> List[int]:
    """Return all Armstrong numbers in the range [0, limit)."""
    return [n for n in range(limit) if is_armstrong(n)]


def main() -> None:
    results: List[int] = find_armstrong_numbers(100_000)
    for number in results:
        print(number)


if __name__ == "__main__":
    main()
