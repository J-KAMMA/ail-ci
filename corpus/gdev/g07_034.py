# task: Write a script that chunks a hardcoded list into overlapping windows of size 4 with a step of 2 and prints each window.
from typing import Sequence, TypeVar

T = TypeVar("T")


def sliding_windows(items: Sequence[T], size: int, step: int) -> list[list[T]]:
    """Return overlapping windows of the given size advancing by step."""
    if size <= 0 or step <= 0:
        raise ValueError("size and step must be positive")
    return [list(items[i:i + size]) for i in range(0, len(items) - size + 1, step)]


def main() -> None:
    data: list[int] = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]
    windows = sliding_windows(data, size=4, step=2)
    for index, window in enumerate(windows):
        print(f"Window {index}: {window}")


if __name__ == "__main__":
    main()
