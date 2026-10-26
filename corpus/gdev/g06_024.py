# task: Write a script that computes the Dice coefficient between two hardcoded sets and prints the rounded value.
from typing import Set, TypeVar

T = TypeVar("T")


def dice_coefficient(a: Set[T], b: Set[T]) -> float:
    """Return the Dice coefficient 2|A∩B| / (|A| + |B|).

    By convention, two empty sets are considered identical and yield 1.0.
    """
    total = len(a) + len(b)
    if total == 0:
        return 1.0
    return 2.0 * len(a & b) / total


def main() -> None:
    set_a: Set[str] = {"apple", "banana", "cherry", "date", "fig"}
    set_b: Set[str] = {"banana", "date", "elderberry", "fig", "grape"}

    score = dice_coefficient(set_a, set_b)
    print(f"Dice coefficient: {round(score, 4)}")


if __name__ == "__main__":
    main()
