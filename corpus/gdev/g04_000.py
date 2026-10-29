# task: Implement bubble sort on a hardcoded list of 20 integers and print the list after each pass.
from typing import List


def bubble_sort_with_passes(values: List[int]) -> List[List[int]]:
    """Sort a copy of the list using bubble sort, recording the list after each pass."""
    data: List[int] = list(values)
    snapshots: List[List[int]] = []
    n: int = len(data)

    for pass_number in range(n - 1):
        swapped: bool = False
        for j in range(n - 1 - pass_number):
            if data[j] > data[j + 1]:
                data[j], data[j + 1] = data[j + 1], data[j]
                swapped = True
        snapshots.append(list(data))
        if not swapped:
            break

    return snapshots


def main() -> None:
    numbers: List[int] = [
        64, 34, 25, 12, 22, 11, 90, 88, 45, 50,
        7, 3, 19, 73, 28, 56, 41, 99, 0, 15,
    ]

    print("Original list:")
    print(numbers)
    print()

    snapshots: List[List[int]] = bubble_sort_with_passes(numbers)

    for index, snapshot in enumerate(snapshots, start=1):
        print(f"After pass {index}: {snapshot}")

    final_list: List[int] = snapshots[-1] if snapshots else list(numbers)
    print()
    print("Sorted list:")
    print(final_list)


if __name__ == "__main__":
    main()
