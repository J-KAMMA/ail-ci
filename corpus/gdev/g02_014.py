# task: List all Pythagorean triples with hypotenuse at most 100 generated from Euclid's formula, without duplicates.
from math import gcd


def euclid_triples(limit: int) -> set[tuple[int, int, int]]:
    """Generate all Pythagorean triples (a, b, c) with c <= limit.

    Primitive triples come from Euclid's formula with m > n > 0,
    gcd(m, n) = 1, and m - n odd. Each primitive triple is scaled by k
    to produce every multiple whose hypotenuse stays within the limit.
    Legs are stored sorted (a < b) and triples are kept in a set, so
    no duplicates appear.
    """
    result: set[tuple[int, int, int]] = set()
    m = 2
    while m * m + 1 <= limit:  # smallest hypotenuse for this m is m^2 + 1 (n = 1)
        for n in range(1, m):
            if (m - n) % 2 == 1 and gcd(m, n) == 1:
                a = m * m - n * n
                b = 2 * m * n
                c = m * m + n * n
                k = 1
                while k * c <= limit:
                    x, y = sorted((k * a, k * b))
                    result.add((x, y, k * c))
                    k += 1
        m += 1
    return result


def main() -> None:
    limit: int = 100
    triples = sorted(euclid_triples(limit), key=lambda t: (t[2], t[0], t[1]))
    print(f"Pythagorean triples with hypotenuse <= {limit}:")
    for a, b, c in triples:
        print(f"{a} {b} {c}")
    print(f"Total: {len(triples)}")


if __name__ == "__main__":
    main()
