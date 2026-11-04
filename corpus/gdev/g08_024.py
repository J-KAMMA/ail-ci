# task: Implement recursive merge sort on a hard-coded list of integers and print the sorted result.
from typing import List


def merge(left: List[int], right: List[int]) -> List[int]:
    """Merge two sorted lists into one sorted list."""
    result: List[int] = []
    i = 0
    j = 0
    while i < len(left) and j < len(right):
        if left[i] <= right[j]:
            result.append(left[i])
            i += 1
        else:
            result.append(right[j])
            j += 1
    result.extend(left[i:])
    result.extend(right[j:])
    return result


def merge_sort(items: List[int]) -> List[int]:
    """Recursively sort a list of integers using merge sort."""
    if len(items) <= 1:
        return list(items)
    mid = len(items) // 2
    left = merge_sort(items[:mid])
    right = merge_sort(items[mid:])
    return merge(left, right)


def main() -> None:
    data: List[int] = [38, 27, 43, 3, 9, 82, 10, -5, 0, 27, 15, 64, -18, 7, 99, 1]
    sorted_data = merge_sort(data)
    print("Original:", data)
    print("Sorted:  ", sorted_data)


if __name__ == "__main__":
    main()
