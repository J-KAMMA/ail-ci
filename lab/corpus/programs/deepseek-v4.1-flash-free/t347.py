import sys
from math import isqrt


def sieve(limit: int) -> list[bool]:
    is_prime = [True] * limit
    if limit > 0:
        is_prime[0] = False
    if limit > 1:
        is_prime[1] = False
    for p in range(2, isqrt(limit - 1) + 1):
        if is_prime[p]:
            for multiple in range(p * p, limit, p):
                is_prime[multiple] = False
    return is_prime


def main() -> None:
    n = int(sys.stdin.readline().strip())
    limit = n * 1000
    size = max(limit, 202)
    is_prime = sieve(size)

    count = sum(1 for i in range(limit) if is_prime[i])
    print(count)

    for p in range(2, 200):
        if p + 2 < 200 and is_prime[p] and is_prime[p + 2]:
            print(f"({p}, {p + 2})")


if __name__ == "__main__":
    main()
