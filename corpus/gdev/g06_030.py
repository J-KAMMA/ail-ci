# task: Write a script that computes the transitive closure of a hardcoded relation represented as a set of pairs and prints it sorted.
from typing import Iterable


HARDCODED_RELATION: set[tuple[str, str]] = {
    ("a", "b"),
    ("b", "c"),
    ("c", "d"),
    ("d", "b"),
    ("e", "a"),
    ("f", "f"),
    ("g", "e"),
}


def transitive_closure(pairs: Iterable[tuple[str, str]]) -> set[tuple[str, str]]:
    """Return the transitive closure of a binary relation given as pairs.

    Uses a Warshall-style approach over the sorted set of elements so the
    result does not depend on set iteration order.
    """
    pair_list = sorted(set(pairs))
    elements = sorted({x for p in pair_list for x in p})
    index = {elem: i for i, elem in enumerate(elements)}
    n = len(elements)

    reach = [[False] * n for _ in range(n)]
    for x, y in pair_list:
        reach[index[x]][index[y]] = True

    for k in range(n):
        row_k = reach[k]
        for i in range(n):
            if reach[i][k]:
                row_i = reach[i]
                for j in range(n):
                    if row_k[j]:
                        row_i[j] = True

    closure: set[tuple[str, str]] = set()
    for i in range(n):
        for j in range(n):
            if reach[i][j]:
                closure.add((elements[i], elements[j]))
    return closure


def format_pairs(pairs: Iterable[tuple[str, str]]) -> list[str]:
    """Format pairs as sorted, human-readable lines."""
    return [f"({x}, {y})" for x, y in sorted(pairs)]


def main() -> None:
    closure = transitive_closure(HARDCODED_RELATION)
    print(f"Original relation size: {len(HARDCODED_RELATION)}")
    print(f"Transitive closure size: {len(closure)}")
    print("Transitive closure (sorted):")
    for line in format_pairs(closure):
        print(line)


if __name__ == "__main__":
    main()
