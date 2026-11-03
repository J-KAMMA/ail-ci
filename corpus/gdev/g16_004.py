# task: Write a recursive generator that flattens arbitrarily nested lists and print the flattened result of a sample structure.
from collections.abc import Iterable, Iterator
from typing import Any


def flatten(items: Iterable[Any]) -> Iterator[Any]:
    """Recursively yield leaf values from arbitrarily nested lists."""
    for item in items:
        if isinstance(item, list):
            yield from flatten(item)
        else:
            yield item


def main() -> None:
    sample: list[Any] = [
        1,
        [2, 3, [4, 5, [6]]],
        [],
        [[7], 8, [[9, [10]]]],
        "eleven",
        [[[12.5]], [True, [None]]],
    ]
    flattened = list(flatten(sample))
    print(flattened)


if __name__ == "__main__":
    main()
