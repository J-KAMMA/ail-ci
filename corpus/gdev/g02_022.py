# task: Solve the Chinese Remainder Theorem for x ≡ 2 (mod 3), x ≡ 3 (mod 5), x ≡ 2 (mod 7), x ≡ 1 (mod 11) and print the smallest solution.
from math import prod


def extended_gcd(a: int, b: int) -> tuple[int, int, int]:
    """Return (g, x, y) such that a*x + b*y = g = gcd(a, b)."""
    if b == 0:
        return a, 1, 0
    g, x1, y1 = extended_gcd(b, a % b)
    return g, y1, x1 - (a // b) * y1


def crt(residues: list[int], moduli: list[int]) -> tuple[int, int]:
    """
    Solve x ≡ residues[i] (mod moduli[i]) for pairwise coprime moduli.
    Returns (smallest non-negative solution, combined modulus).
    """
    if len(residues) != len(moduli):
        raise ValueError("residues and moduli must have the same length")

    total_modulus = prod(moduli)
    x = 0
    for r, m in zip(residues, moduli):
        other = total_modulus // m
        # Inverse of `other` modulo m; gcd is 1 because moduli are pairwise coprime.
        g, inv, _ = extended_gcd(other % m, m)
        if g != 1:
            raise ValueError("moduli must be pairwise coprime")
        x += r * inv * other
    return x % total_modulus, total_modulus


def main() -> None:
    residues: list[int] = [2, 3, 2, 1]
    moduli: list[int] = [3, 5, 7, 11]

    solution, modulus = crt(residues, moduli)
    print(f"Smallest solution: x = {solution} (mod {modulus})")


if __name__ == "__main__":
    main()
