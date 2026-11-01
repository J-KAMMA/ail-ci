# task: Write a script that merges two hardcoded sorted lists into one sorted list without using the sorted() function.
from typing import List


def merge_sorted(left: List[int], right: List[int]) -> List[int]:
    """Merge two sorted lists into a new sorted list using a two-pointer approach."""
    merged: List[int] = []
    i: int = 0
    j: int = 0

    while i < len(left) and j < len(right):
        if left[i] <= right[j]:
            merged.append(left[i])
            i += 1
        else:
            merged.append(right[j])
            j += 1

    merged.extend(left[i:])
    merged.extend(right[j:])
    return merged


def main() -> None:
    list_a: List[int] = [1, 4, 7, 10, 15, 21]
    list_b: List[int] = [2, 3, 8, 9, 16, 22, 30]

    result: List[int] = merge_sorted(list_a, list_b)
    print("First list: ", list_a)
    print("Second list:", list_b)
    print("Merged list:", result)


if __name__ == "__main__":
    main()
