# task: Use itertools.combinations to find all 3-element subsets of a hardcoded list of numbers that sum to zero and print them.
from itertools import combinations


NUMBERS: list[int] = [-7, -5, -3, -1, 0, 1, 2, 4, 6, 8, 10, -2, 3, -4, 5, -6]


def find_zero_sum_triples(numbers: list[int]) -> list[tuple[int, int, int]]:
    """Return all 3-element combinations whose elements sum to zero."""
    return [triple for triple in combinations(numbers, 3) if sum(triple) == 0]


def main() -> None:
    triples = find_zero_sum_triples(NUMBERS)
    print(f"Numbers: {NUMBERS}")
    print(f"Found {len(triples)} triple(s) summing to zero:")
    for triple in triples:
        print(triple)


if __name__ == "__main__":
    main()
