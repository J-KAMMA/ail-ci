# task: Write a script that builds two hardcoded sets of integers, computes their union, and prints the sorted result.
from typing import Set


def build_first_set() -> Set[int]:
    return {1, 3, 5, 7, 9, 11, 13}


def build_second_set() -> Set[int]:
    return {2, 3, 5, 8, 13, 21}


def main() -> None:
    first: Set[int] = build_first_set()
    second: Set[int] = build_second_set()
    union: Set[int] = first | second
    print(sorted(union))


if __name__ == "__main__":
    main()
