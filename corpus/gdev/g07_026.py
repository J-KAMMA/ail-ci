# task: Write a script that finds all pairs of numbers in a hardcoded list that sum to a target value and prints them without repetition.
from typing import Iterable


NUMBERS: list[int] = [2, 4, 3, 5, 7, 8, 8, 1, 6, -2, 0, 9, 4, 3, 10, -1, 5]
TARGET: int = 10


def find_pairs(numbers: Iterable[int], target: int) -> list[tuple[int, int]]:
    """Return unique pairs (a, b) with a + b == target, each pair sorted, list sorted."""
    seen: set[int] = set()
    pairs: set[tuple[int, int]] = set()
    for value in numbers:
        complement = target - value
        if complement in seen:
            pairs.add((min(value, complement), max(value, complement)))
        seen.add(value)
    return sorted(pairs)


def main() -> None:
    pairs = find_pairs(NUMBERS, TARGET)
    print(f"Numbers: {NUMBERS}")
    print(f"Target: {TARGET}")
    if not pairs:
        print("No pairs found.")
        return
    for a, b in pairs:
        print(f"{a} + {b} = {TARGET}")


if __name__ == "__main__":
    main()
