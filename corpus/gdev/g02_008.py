# task: Compute Euler's totient for all integers from 1 to 1000 and print the n that maximizes n/φ(n).
from fractions import Fraction


def totient(n: int) -> int:
    """Return Euler's totient function phi(n) for n >= 1."""
    result = n
    remaining = n
    p = 2
    while p * p <= remaining:
        if remaining % p == 0:
            while remaining % p == 0:
                remaining //= p
            result -= result // p
        p += 1
    if remaining > 1:
        result -= result // remaining
    return result


def main() -> None:
    limit = 1000
    best_n = 1
    best_ratio = Fraction(1, totient(1))

    for n in range(2, limit + 1):
        ratio = Fraction(n, totient(n))
        if ratio > best_ratio:
            best_ratio = ratio
            best_n = n

    print(best_n)


if __name__ == "__main__":
    main()
