# task: Write a script that verifies the distributive law of intersection over union for three hardcoded sets and prints True or False.
from typing import Set


def main() -> None:
    # Three hardcoded sets
    a: Set[int] = {1, 2, 3, 4, 5}
    b: Set[int] = {4, 5, 6, 7}
    c: Set[int] = {3, 5, 7, 9}

    # Distributive law: A ∩ (B ∪ C) == (A ∩ B) ∪ (A ∩ C)
    left: Set[int] = a & (b | c)
    right: Set[int] = (a & b) | (a & c)

    print(left == right)


if __name__ == "__main__":
    main()
