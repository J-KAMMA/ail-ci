# task: Write a script that determines which of several hardcoded sets are pairwise disjoint and prints the index pairs.
from itertools import combinations
from typing import Final


SETS: Final[list[frozenset[str]]] = [
    frozenset({"apple", "banana", "cherry"}),
    frozenset({"dog", "elephant", "fox"}),
    frozenset({"banana", "grape"}),
    frozenset({"kiwi", "lemon"}),
    frozenset({"fox", "goat", "horse"}),
    frozenset({"mango", "nectarine", "olive"}),
    frozenset({"apple", "papaya"}),
    frozenset({"quince", "raspberry", "strawberry"}),
]


def disjoint_pairs(sets: list[frozenset[str]]) -> list[tuple[int, int]]:
    """Return sorted index pairs (i, j) with i < j whose sets are disjoint."""
    result: list[tuple[int, int]] = []
    for (i, a), (j, b) in combinations(enumerate(sets), 2):
        if a.isdisjoint(b):
            result.append((i, j))
    return result


def main() -> None:
    pairs = disjoint_pairs(SETS)
    print(f"Number of sets: {len(SETS)}")
    print(f"Number of pairwise disjoint pairs: {len(pairs)}")
    for i, j in pairs:
        print(f"Sets {i} and {j} are disjoint")


if __name__ == "__main__":
    main()
