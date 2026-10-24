# task: Find all twin prime pairs below 10,000 and print their count and the largest pair.
from __future__ import annotations


LIMIT: int = 10_000


def sieve(limit: int) -> list[bool]:
    """Return a list where index i is True if i is prime, for 0 <= i < limit."""
    is_prime: list[bool] = [True] * limit
    is_prime[0] = False
    if limit > 1:
        is_prime[1] = False
    i: int = 2
    while i * i < limit:
        if is_prime[i]:
            for multiple in range(i * i, limit, i):
                is_prime[multiple] = False
        i += 1
    return is_prime


def find_twin_primes(limit: int) -> list[tuple[int, int]]:
    """Return all twin prime pairs (p, p + 2) with both members below limit."""
    is_prime: list[bool] = sieve(limit)
    pairs: list[tuple[int, int]] = []
    for p in range(2, limit - 2):
        if is_prime[p] and is_prime[p + 2]:
            pairs.append((p, p + 2))
    return pairs


def main() -> None:
    pairs: list[tuple[int, int]] = find_twin_primes(LIMIT)
    count: int = len(pairs)
    largest: tuple[int, int] = pairs[-1]
    print(f"Twin prime pairs below {LIMIT}: {count}")
    print(f"Largest pair: {largest}")


if __name__ == "__main__":
    main()
