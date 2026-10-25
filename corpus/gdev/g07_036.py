# task: Write a script that removes the largest and smallest values from a hardcoded list in one pass and prints the trimmed list.
from typing import Optional


def trim_extremes(values: list[int]) -> list[int]:
    """Remove one smallest and one largest value from the list in a single pass."""
    if not values:
        return []

    min_index: int = 0
    max_index: int = 0

    # Single pass: track indices of the minimum (first occurrence) and
    # maximum (last occurrence) so that they are distinct when possible.
    for index, value in enumerate(values):
        if value < values[min_index]:
            min_index = index
        if value >= values[max_index]:
            max_index = index

    excluded: set[int] = {min_index, max_index}
    return [value for index, value in enumerate(values) if index not in excluded]


def main() -> None:
    data: list[int] = [42, 7, 19, 88, 3, 56, 3, 91, 27, 88, 14]
    print("Original:", data)
    trimmed: list[int] = trim_extremes(data)
    print("Trimmed: ", trimmed)


if __name__ == "__main__":
    main()
