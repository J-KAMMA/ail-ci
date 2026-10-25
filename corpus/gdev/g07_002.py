# task: Write a script that rotates a fixed list of 10 elements left by 3 positions using only slicing and prints the result.
from typing import Sequence


def rotate_left(items: Sequence[int], k: int) -> list[int]:
    """Return a new list rotated left by k positions using slicing only."""
    n = len(items)
    if n == 0:
        return []
    k %= n
    return list(items[k:]) + list(items[:k])


def main() -> None:
    data: list[int] = [0, 1, 2, 3, 4, 5, 6, 7, 8, 9]
    rotated: list[int] = rotate_left(data, 3)
    print(rotated)


if __name__ == "__main__":
    main()
