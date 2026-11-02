# task: Implement selection sort on a predefined list of floats and print the swap count along with the final order.
from typing import List


def selection_sort(items: List[float]) -> int:
    """Sort the list in place using selection sort and return the number of swaps made."""
    swap_count: int = 0
    n: int = len(items)
    for i in range(n - 1):
        min_index: int = i
        for j in range(i + 1, n):
            if items[j] < items[min_index]:
                min_index = j
        if min_index != i:
            items[i], items[min_index] = items[min_index], items[i]
            swap_count += 1
    return swap_count


def main() -> None:
    data: List[float] = [3.7, -1.2, 9.5, 0.0, 2.25, -8.4, 5.1, 2.25, 7.03, -0.5]
    print("Original list:", data)
    swaps: int = selection_sort(data)
    print("Swap count:", swaps)
    print("Sorted list:", data)


if __name__ == "__main__":
    main()
