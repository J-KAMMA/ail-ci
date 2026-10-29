# task: Compute the continued fraction expansion of √61, then print its period length and first ten terms.
from math import isqrt


def sqrt_continued_fraction(n: int) -> tuple[int, list[int]]:
    """Return (a0, period) for the continued fraction of sqrt(n).

    The full expansion is [a0; period repeated forever].
    For a perfect square the period is empty.
    """
    a0 = isqrt(n)
    if a0 * a0 == n:
        return a0, []

    m, d, a = 0, 1, a0
    period: list[int] = []
    while True:
        m = d * a - m
        d = (n - m * m) // d
        a = (a0 + m) // d
        period.append(a)
        if a == 2 * a0:
            break
    return a0, period


def first_terms(a0: int, period: list[int], count: int) -> list[int]:
    """Return the first `count` terms of the continued fraction expansion."""
    terms: list[int] = [a0]
    i = 0
    while len(terms) < count:
        terms.append(period[i % len(period)])
        i += 1
    return terms[:count]


def main() -> None:
    n: int = 61
    a0, period = sqrt_continued_fraction(n)
    terms = first_terms(a0, period, 10)

    print(f"Continued fraction of sqrt({n}):")
    print(f"Period length: {len(period)}")
    print(f"First ten terms: {terms}")


if __name__ == "__main__":
    main()
