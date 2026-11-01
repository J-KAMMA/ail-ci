# task: Write a script that computes the running maximum of a hardcoded list and prints the list of running maxima.
from typing import Sequence


def running_maximum(values: Sequence[int]) -> list[int]:
    """Return the running maximum of a sequence of integers."""
    result: list[int] = []
    current: int | None = None
    for value in values:
        if current is None or value > current:
            current = value
        result.append(current)
    return result


def main() -> None:
    data: list[int] = [3, 1, 4, 1, 5, 9, 2, 6, 5, 3, 5, 8, 9, 7, 9]
    maxima: list[int] = running_maximum(data)
    print(maxima)


if __name__ == "__main__":
    main()
