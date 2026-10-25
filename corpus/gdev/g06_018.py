# task: Write a script that builds a frozenset of hardcoded tuples and demonstrates it is hashable by using it as a dictionary key.
from typing import Dict, FrozenSet, Tuple


def build_frozenset() -> FrozenSet[Tuple[int, str]]:
    """Build a frozenset of hardcoded (int, str) tuples."""
    return frozenset(
        {
            (1, "alpha"),
            (2, "beta"),
            (3, "gamma"),
            (4, "delta"),
            (5, "epsilon"),
        }
    )


def main() -> None:
    fs: FrozenSet[Tuple[int, str]] = build_frozenset()

    # Demonstrate that the frozenset is hashable.
    print("hash(frozenset) is an int:", isinstance(hash(fs), int))

    # Use the frozenset as a dictionary key.
    registry: Dict[FrozenSet[Tuple[int, str]], str] = {}
    registry[fs] = "primary configuration"

    # An equal frozenset built separately maps to the same key.
    same_contents: FrozenSet[Tuple[int, str]] = frozenset(
        [(5, "epsilon"), (4, "delta"), (3, "gamma"), (2, "beta"), (1, "alpha")]
    )
    print("equal frozensets:", fs == same_contents)
    print("lookup with equal frozenset:", registry[same_contents])

    # Membership checks on the key itself.
    print("contains (3, 'gamma'):", (3, "gamma") in fs)
    print("contains (9, 'omega'):", (9, "omega") in fs)

    # Sorted output keeps the printed order deterministic.
    for item in sorted(fs):
        print("item:", item)

    print("dictionary size:", len(registry))


if __name__ == "__main__":
    main()
