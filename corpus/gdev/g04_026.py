# task: Count the number of inversions in a fixed list using merge sort and print the total inversion count.
from typing import List, Tuple


def merge_count(left: List[int], right: List[int]) -> Tuple[List[int], int]:
    """Merge two sorted lists and count cross inversions between them."""
    merged: List[int] = []
    i = 0
    j = 0
    inversions = 0
    while i < len(left) and j < len(right):
        if left[i] <= right[j]:
            merged.append(left[i])
            i += 1
        else:
            # right[j] is smaller than every remaining element in left
            merged.append(right[j])
            inversions += len(left) - i
            j += 1
    merged.extend(left[i:])
    merged.extend(right[j:])
    return merged, inversions


def sort_and_count(arr: List[int]) -> Tuple[List[int], int]:
    """Sort the list with merge sort and return (sorted list, inversion count)."""
    n = len(arr)
    if n <= 1:
        return list(arr), 0
    mid = n // 2
    left, inv_left = sort_and_count(arr[:mid])
    right, inv_right = sort_and_count(arr[mid:])
    merged, inv_split = merge_count(left, right)
    return merged, inv_left + inv_right + inv_split


def count_inversions(arr: List[int]) -> int:
    """Return the number of pairs (i, j) with i < j and arr[i] > arr[j]."""
    _, total = sort_and_count(arr)
    return total


def main() -> None:
    data: List[int] = [
        37, 12, 89, 4, 56, 23, 71, 8, 94, 15,
        62, 3, 48, 27, 80, 19, 65, 2, 33, 77,
        10, 58, 41, 96, 6, 84, 29, 51, 14, 90,
    ]
    total = count_inversions(data)
    print(f"Number of elements: {len(data)}")
    print(f"Total inversions: {total}")


if __name__ == "__main__":
    main()
