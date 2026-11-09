# task: Implement binary search iteratively on a hardcoded sorted list and print each low, mid, and high index visited.
from typing import Sequence


def binary_search_trace(items: Sequence[int], target: int) -> int:
    """Iteratively binary search `items` for `target`, printing each low, mid, high visited.

    Returns the index of target if found, otherwise -1.
    """
    low: int = 0
    high: int = len(items) - 1

    while low <= high:
        mid: int = (low + high) // 2
        print(f"low={low} mid={mid} high={high}")

        if items[mid] == target:
            return mid
        if items[mid] < target:
            low = mid + 1
        else:
            high = mid - 1

    return -1


def main() -> None:
    sorted_values: list[int] = [2, 5, 8, 12, 16, 23, 38, 56, 72, 91]
    targets: list[int] = [23, 2, 91, 7]

    for target in targets:
        print(f"Searching for {target}:")
        index: int = binary_search_trace(sorted_values, target)
        if index != -1:
            print(f"Found {target} at index {index}")
        else:
            print(f"{target} not found")
        print()


if __name__ == "__main__":
    main()
