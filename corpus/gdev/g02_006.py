# task: Compute the modular inverses of 3 modulo 11 and 17 using pow with exponent -1 and print them.
from typing import Sequence


def modular_inverses(base: int, moduli: Sequence[int]) -> list[tuple[int, int]]:
    """Return (modulus, inverse) pairs for base modulo each modulus."""
    return [(m, pow(base, -1, m)) for m in moduli]


def main() -> None:
    base: int = 3
    moduli: list[int] = [11, 17]
    for modulus, inverse in modular_inverses(base, moduli):
        print(f"The inverse of {base} modulo {modulus} is {inverse}")


if __name__ == "__main__":
    main()
