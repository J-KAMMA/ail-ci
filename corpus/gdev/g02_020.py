# task: Find the smallest primitive root modulo 101 and print it.
def prime_factors(n: int) -> set[int]:
    """Return the set of distinct prime factors of n."""
    factors: set[int] = set()
    d = 2
    while d * d <= n:
        while n % d == 0:
            factors.add(d)
            n //= d
        d += 1
    if n > 1:
        factors.add(n)
    return factors


def is_primitive_root(g: int, p: int) -> bool:
    """Check whether g is a primitive root modulo the prime p."""
    phi = p - 1
    for q in prime_factors(phi):
        if pow(g, phi // q, p) == 1:
            return False
    return True


def smallest_primitive_root(p: int) -> int:
    """Return the smallest primitive root modulo the prime p."""
    for g in range(2, p):
        if is_primitive_root(g, p):
            return g
    raise ValueError(f"no primitive root found for {p}")


def main() -> None:
    p: int = 101
    print(smallest_primitive_root(p))


if __name__ == "__main__":
    main()
