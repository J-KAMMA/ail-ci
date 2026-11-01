# task: Write a script that checks whether one hardcoded set is a subset of another and prints the boolean result.
from typing import Set


def is_subset(a: Set[str], b: Set[str]) -> bool:
    """Return True if every element of a is also in b."""
    return a <= b


def main() -> None:
    first: Set[str] = {"apple", "banana", "cherry"}
    second: Set[str] = {"apple", "banana", "cherry", "date", "elderberry"}

    print(is_subset(first, second))


if __name__ == "__main__":
    main()
