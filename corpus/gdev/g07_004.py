# task: Write a script that flattens a hardcoded nested list of lists up to two levels deep and prints the flat result.
from typing import Any


def flatten_two_levels(data: list[Any]) -> list[Any]:
    """Flatten a list of lists up to two levels deep.

    Level-one elements that are lists are expanded into their items.
    Items inside those sublists that are themselves lists are not expanded
    further; they are kept as-is, since only two levels are flattened.
    """
    result: list[Any] = []
    for item in data:
        if isinstance(item, list):
            result.extend(item)
        else:
            result.append(item)
    return result


def main() -> None:
    nested: list[Any] = [
        [1, 2, 3],
        [4, [5, 6], 7],
        8,
        [9, 10],
        "eleven",
        [[12, 13], 14],
    ]
    flat = flatten_two_levels(nested)
    print(flat)


if __name__ == "__main__":
    main()
