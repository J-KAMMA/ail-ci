# task: Implement recursive binary search on a fixed sorted list and print the index found for several target values.
from typing import Sequence


def binary_search(items: Sequence[int], target: int, low: int, high: int) -> int:
    """Recursively search items[low:high+1] for target.

    Returns the index of target if found, otherwise -1.
    """
    if low > high:
        return -1
    mid = (low + high) // 2
    if items[mid] == target:
        return mid
    if items[mid] < target:
        return binary_search(items, target, mid + 1, high)
    return binary_search(items, target, low, mid - 1)


def search(items: Sequence[int], target: int) -> int:
    """Convenience wrapper for recursive binary search over the whole list."""
    return binary_search(items, target, 0, len(items) - 1)


def main() -> None:
    sorted_values: list[int] = [2, 3, 5, 7, 11, 13, 17, 19, 23, 29, 31, 37, 41]
    targets: list[int] = [1, 2, 13, 29, 41, 4, 37, 50, 17]

    print(f"Sorted list: {sorted_values}")
    for target in targets:
        index: int = search(sorted_values, target)
        if index >= 0:
            print(f"Target {target}: found at index {index}")
        else:
            print(f"Target {target}: not found (index {index})")


if __name__ == "__main__":
    main()
