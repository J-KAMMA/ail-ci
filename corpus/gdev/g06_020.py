# task: Write a script that partitions a hardcoded set of integers into evens and odds using set comprehensions and prints both.
from typing import Set


def partition_evens_odds(numbers: Set[int]) -> tuple[Set[int], Set[int]]:
    """Split a set of integers into (evens, odds) using set comprehensions."""
    evens: Set[int] = {n for n in numbers if n % 2 == 0}
    odds: Set[int] = {n for n in numbers if n % 2 != 0}
    return evens, odds


def main() -> None:
    data: Set[int] = {12, 7, 3, 18, 25, 0, -4, 9, 42, -15, 16, 1}
    evens, odds = partition_evens_odds(data)
    print("Evens:", sorted(evens))
    print("Odds:", sorted(odds))


if __name__ == "__main__":
    main()
