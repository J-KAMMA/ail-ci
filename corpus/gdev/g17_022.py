# task: Flatten an arbitrarily nested list recursively using map and filter, then print the flat result.
from typing import Any


def flatten(nested: list[Any]) -> list[Any]:
    """Recursively flatten an arbitrarily nested list using map and filter."""
    # Turn each element into a flat list: recurse into sublists, wrap scalars.
    flattened_parts = map(
        lambda item: flatten(item) if isinstance(item, list) else [item],
        nested,
    )
    # Drop empty parts (from empty sublists) so they contribute nothing.
    non_empty_parts = filter(lambda part: len(part) > 0, flattened_parts)

    result: list[Any] = []
    for part in non_empty_parts:
        result.extend(part)
    return result


def main() -> None:
    data: list[Any] = [
        1,
        [2, 3, [4, [5, 6]], []],
        [[7], [[8, [9]]]],
        "ten",
        [[], [[[11]]], 12],
    ]

    print("Original:", data)
    print("Flattened:", flatten(data))


if __name__ == "__main__":
    main()
