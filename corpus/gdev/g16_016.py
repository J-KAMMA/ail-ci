# task: Implement a round-robin generator that interleaves elements from three fixed lists of different lengths and print the result.
from itertools import zip_longest
from typing import Iterable, Iterator, TypeVar

T = TypeVar("T")

_SENTINEL = object()


def round_robin(*iterables: Iterable[T]) -> Iterator[T]:
    """Yield elements from each iterable in turn, skipping exhausted ones."""
    for group in zip_longest(*iterables, fillvalue=_SENTINEL):
        for item in group:
            if item is not _SENTINEL:
                yield item  # type: ignore[misc]


def main() -> None:
    letters: list[str] = ["a", "b", "c", "d", "e"]
    numbers: list[int] = [1, 2, 3]
    symbols: list[str] = ["#", "$", "%", "&"]

    result: list[object] = list(round_robin(letters, numbers, symbols))
    print("Round-robin result:")
    print(result)

    print("Joined as text:")
    print(" ".join(str(x) for x in result))


if __name__ == "__main__":
    main()
