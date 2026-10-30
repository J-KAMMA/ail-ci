# task: Implement a generator that yields sliding windows of size 3 over a fixed list and print each window.
from collections.abc import Iterator, Sequence


def sliding_windows(items: Sequence[int], size: int = 3) -> Iterator[tuple[int, ...]]:
    """Yield consecutive windows of the given size over items."""
    if size <= 0:
        raise ValueError("window size must be positive")
    for start in range(len(items) - size + 1):
        yield tuple(items[start:start + size])


def main() -> None:
    data: list[int] = [1, 2, 3, 4, 5, 6, 7, 8]
    for window in sliding_windows(data, 3):
        print(window)


if __name__ == "__main__":
    main()
