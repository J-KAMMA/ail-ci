# task: Create a dictionary counting primes below 500 grouped by their last digit and print the counts.
from typing import Dict


def is_prime(n: int) -> bool:
    if n < 2:
        return False
    if n < 4:
        return True
    if n % 2 == 0 or n % 3 == 0:
        return False
    i = 5
    while i * i <= n:
        if n % i == 0 or n % (i + 2) == 0:
            return False
        i += 6
    return True


def count_primes_by_last_digit(limit: int) -> Dict[int, int]:
    counts: Dict[int, int] = {digit: 0 for digit in range(10)}
    for n in range(2, limit):
        if is_prime(n):
            counts[n % 10] += 1
    return counts


def main() -> None:
    counts = count_primes_by_last_digit(500)
    for digit in sorted(counts):
        print(f"Last digit {digit}: {counts[digit]}")
    print(f"Total primes below 500: {sum(counts.values())}")


if __name__ == "__main__":
    main()
