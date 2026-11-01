# task: Compute the sum of all primes below 2,000,000 using a Sieve of Eratosthenes and print the result.
from __future__ import annotations


def sieve_of_eratosthenes(limit: int) -> bytearray:
    """Return a bytearray where index i is 1 if i is prime (for i < limit)."""
    is_prime = bytearray([1]) * limit
    if limit > 0:
        is_prime[0] = 0
    if limit > 1:
        is_prime[1] = 0
    p = 2
    while p * p < limit:
        if is_prime[p]:
            start = p * p
            step = p
            count = len(range(start, limit, step))
            is_prime[start:limit:step] = bytes(count)
        p += 1
    return is_prime


def sum_of_primes_below(limit: int) -> int:
    """Sum all primes strictly less than limit."""
    is_prime = sieve_of_eratosthenes(limit)
    total = 0
    for n in range(2, limit):
        if is_prime[n]:
            total += n
    return total


def main() -> None:
    limit: int = 2_000_000
    result: int = sum_of_primes_below(limit)
    print(result)


if __name__ == "__main__":
    main()
