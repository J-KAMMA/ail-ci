# task: Recursively generate all subsets of {1, 2, 3, 4, 5} and print them sorted by size and then lexicographically.
from typing import Sequence


def generate_subsets(elements: Sequence[int]) -> list[tuple[int, ...]]:
    """Recursively generate all subsets of the given elements as sorted tuples."""
    if not elements:
        return [()]
    first = elements[0]
    rest = elements[1:]
    without_first = generate_subsets(rest)
    with_first = [(first,) + subset for subset in without_first]
    return without_first + with_first


def format_subset(subset: tuple[int, ...]) -> str:
    """Format a subset as a set-like string, e.g. {1, 3}."""
    return "{" + ", ".join(str(x) for x in subset) + "}"


def main() -> None:
    universe: list[int] = [1, 2, 3, 4, 5]
    subsets = generate_subsets(universe)
    subsets.sort(key=lambda s: (len(s), s))
    for subset in subsets:
        print(format_subset(subset))


if __name__ == "__main__":
    main()
