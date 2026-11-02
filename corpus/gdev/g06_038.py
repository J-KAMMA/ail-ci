# task: Write a script that computes the set of all distinct sums obtained from choosing two different elements of a hardcoded integer set and prints it sorted.
from itertools import combinations


NUMBERS: frozenset[int] = frozenset({1, 3, 4, 7, 10, 12, 15, 20})


def distinct_pair_sums(values: frozenset[int]) -> list[int]:
    """Return the sorted list of distinct sums of two different elements."""
    sums: set[int] = {a + b for a, b in combinations(sorted(values), 2)}
    return sorted(sums)


def main() -> None:
    result: list[int] = distinct_pair_sums(NUMBERS)
    print(result)


if __name__ == "__main__":
    main()
