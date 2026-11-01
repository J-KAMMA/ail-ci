# task: Write a script that determines whether a hardcoded set is a proper superset of another hardcoded set and prints the result.
from typing import Set


def is_proper_superset(a: Set[str], b: Set[str]) -> bool:
    """Return True if a is a proper superset of b (a ⊇ b and a != b)."""
    return a > b


def main() -> None:
    set_a: Set[str] = {"apple", "banana", "cherry", "date"}
    set_b: Set[str] = {"banana", "cherry"}

    result = is_proper_superset(set_a, set_b)

    print(f"Set A: {', '.join(sorted(set_a))}")
    print(f"Set B: {', '.join(sorted(set_b))}")
    print(f"Is A a proper superset of B? {result}")


if __name__ == "__main__":
    main()
