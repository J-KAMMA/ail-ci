# task: Write a script that removes every occurrence of a given value from a hardcoded list using slice assignment and list comprehension, then prints the result.
from typing import List


def remove_all(items: List[int], value: int) -> None:
    """Remove every occurrence of value from items in place using slice assignment."""
    items[:] = [x for x in items if x != value]


def main() -> None:
    numbers: List[int] = [3, 1, 4, 1, 5, 9, 1, 2, 6, 1, 5, 3]
    target: int = 1

    print(f"Original: {numbers}")
    remove_all(numbers, target)
    print(f"After removing {target}: {numbers}")


if __name__ == "__main__":
    main()
