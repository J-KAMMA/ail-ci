# task: Implement quicksort using the Lomuto partition scheme on a fixed array and print the pivot chosen at each recursive call.
from typing import Sequence


def lomuto_partition(arr: list[int], lo: int, hi: int) -> int:
    """Partition arr[lo..hi] around the last element and return its final index."""
    pivot: int = arr[hi]
    i: int = lo - 1
    for j in range(lo, hi):
        if arr[j] <= pivot:
            i += 1
            arr[i], arr[j] = arr[j], arr[i]
    arr[i + 1], arr[hi] = arr[hi], arr[i + 1]
    return i + 1


def quicksort(arr: list[int], lo: int, hi: int, depth: int = 0) -> None:
    """Sort arr[lo..hi] in place using Lomuto partitioning, printing each pivot."""
    if lo < hi:
        pivot_value: int = arr[hi]
        print(
            f"depth={depth} subarray=[{lo}..{hi}] "
            f"pivot={pivot_value} (index {hi})"
        )
        p: int = lomuto_partition(arr, lo, hi)
        quicksort(arr, lo, p - 1, depth + 1)
        quicksort(arr, p + 1, hi, depth + 1)


def is_sorted(seq: Sequence[int]) -> bool:
    return all(seq[k] <= seq[k + 1] for k in range(len(seq) - 1))


def main() -> None:
    data: list[int] = [38, 27, 43, 3, 9, 82, 10, 3, 55, 21]
    print(f"input:  {data}")
    quicksort(data, 0, len(data) - 1)
    print(f"output: {data}")
    print(f"sorted correctly: {is_sorted(data)}")


if __name__ == "__main__":
    main()
