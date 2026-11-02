# task: Merge k fixed sorted lists into one sorted list using a min-heap and print the merged output.
import heapq
from typing import List


def merge_k_sorted_lists(lists: List[List[int]]) -> List[int]:
    """Merge k sorted lists into one sorted list using a min-heap."""
    heap: List[tuple[int, int, int]] = []
    # Heap entries: (value, list_index, element_index)
    for list_idx, lst in enumerate(lists):
        if lst:
            heapq.heappush(heap, (lst[0], list_idx, 0))

    merged: List[int] = []
    while heap:
        value, list_idx, elem_idx = heapq.heappop(heap)
        merged.append(value)
        next_idx = elem_idx + 1
        if next_idx < len(lists[list_idx]):
            heapq.heappush(heap, (lists[list_idx][next_idx], list_idx, next_idx))
    return merged


def main() -> None:
    fixed_lists: List[List[int]] = [
        [1, 4, 7, 10],
        [2, 2, 5, 8, 12],
        [0, 3, 6, 9, 11, 15],
        [],
        [-5, 13, 14],
    ]

    print("Input lists:")
    for i, lst in enumerate(fixed_lists):
        print(f"  list {i}: {lst}")

    merged = merge_k_sorted_lists(fixed_lists)
    print("Merged output:")
    print(merged)


if __name__ == "__main__":
    main()
