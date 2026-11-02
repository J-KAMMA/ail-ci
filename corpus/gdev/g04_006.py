# task: Implement heapsort on a hardcoded list of integers without using the heapq module and print the heap state after building the max-heap.
from typing import List


def sift_down(arr: List[int], start: int, end: int) -> None:
    """Restore the max-heap property for the subtree rooted at `start`.

    `end` is the exclusive upper bound of the heap region in `arr`.
    """
    root = start
    while True:
        left = 2 * root + 1
        if left >= end:
            break
        right = left + 1
        largest = root
        if arr[left] > arr[largest]:
            largest = left
        if right < end and arr[right] > arr[largest]:
            largest = right
        if largest == root:
            break
        arr[root], arr[largest] = arr[largest], arr[root]
        root = largest


def build_max_heap(arr: List[int]) -> None:
    """Rearrange `arr` in place into a max-heap in O(n) time."""
    n = len(arr)
    for start in range(n // 2 - 1, -1, -1):
        sift_down(arr, start, n)


def heapsort(arr: List[int]) -> None:
    """Sort `arr` in ascending order in place using heapsort."""
    n = len(arr)
    build_max_heap(arr)
    for end in range(n - 1, 0, -1):
        arr[0], arr[end] = arr[end], arr[0]
        sift_down(arr, 0, end)


def main() -> None:
    data: List[int] = [38, 27, 43, 3, 9, 82, 10, -5, 27, 0, 61, 14]

    heap: List[int] = data.copy()
    build_max_heap(heap)
    print("Max-heap after building:", heap)

    is_valid = all(
        heap[parent] >= heap[child]
        for child in range(1, len(heap))
        for parent in [(child - 1) // 2]
    )
    print("Max-heap property holds:", is_valid)

    sorted_data: List[int] = data.copy()
    heapsort(sorted_data)
    print("Sorted result:", sorted_data)
    print("Matches built-in sorted():", sorted_data == sorted(data))


if __name__ == "__main__":
    main()
