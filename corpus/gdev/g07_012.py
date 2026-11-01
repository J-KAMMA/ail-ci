# task: Write a script that performs an in-place bubble sort on a hardcoded list and prints the list after each full pass.
from typing import List


def bubble_sort_with_passes(items: List[int]) -> None:
    """Sort the list in place using bubble sort, printing it after each full pass."""
    n = len(items)
    for pass_number in range(1, n):
        swapped = False
        for j in range(n - pass_number):
            if items[j] > items[j + 1]:
                items[j], items[j + 1] = items[j + 1], items[j]
                swapped = True
        print(f"After pass {pass_number}: {items}")
        if not swapped:
            break


def main() -> None:
    data: List[int] = [64, 34, 25, 12, 22, 11, 90, 5]
    print(f"Original: {data}")
    bubble_sort_with_passes(data)
    print(f"Sorted:   {data}")


if __name__ == "__main__":
    main()
