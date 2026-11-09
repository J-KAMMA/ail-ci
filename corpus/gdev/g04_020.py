# task: Implement exponential search on a fixed sorted list and print the range doubling steps before the binary search phase.
from typing import Sequence


def exponential_search(arr: Sequence[int], target: int) -> int:
    """Return the index of target in sorted arr, or -1 if absent.

    Phase 1 doubles the bound until arr[bound] >= target (or the end is reached).
    Phase 2 runs binary search within the located range.
    """
    n = len(arr)
    if n == 0:
        print("List is empty; target not found.")
        return -1

    print(f"Searching for {target} in list of length {n}")
    print("--- Exponential (range doubling) phase ---")

    if arr[0] == target:
        print(f"  Found at index 0 during range check")
        return 0

    bound = 1
    step = 1
    while bound < n and arr[bound] < target:
        print(f"  step {step}: arr[{bound}] = {arr[bound]} < {target}, doubling bound {bound} -> {min(bound * 2, n - 1) if bound * 2 < n else n - 1}")
        bound *= 2
        step += 1

    low = bound // 2
    high = min(bound, n - 1)
    if bound < n and arr[bound] < target:
        high = n - 1
    print(f"  stopped: arr[{min(bound, n - 1)}] = {arr[min(bound, n - 1)]} "
          f">= {target} or end of list reached")
    print(f"Range for binary search: [{low}, {high}]")

    print("--- Binary search phase ---")
    result = _binary_search(arr, target, low, high)
    return result


def _binary_search(arr: Sequence[int], target: int, low: int, high: int) -> int:
    """Binary search for target in arr[low:high+1]; return index or -1."""
    lo, hi = low, high
    while lo <= hi:
        mid = (lo + hi) // 2
        value = arr[mid]
        print(f"  check mid={mid}, arr[mid]={value}")
        if value == target:
            print(f"  Found {target} at index {mid}")
            return mid
        if value < target:
            lo = mid + 1
        else:
            hi = mid - 1
    print(f"  {target} not found")
    return -1


def main() -> None:
    data: list[int] = [2, 3, 5, 7, 11, 13, 17, 19, 23, 29, 31, 37, 41, 43, 47, 53, 59, 61, 67, 71]
    print(f"Sorted list: {data}")
    print()

    targets = [43, 2, 71, 30, 1, 17]
    for target in targets:
        index = exponential_search(data, target)
        print(f"Result for {target}: index {index}")
        print()


if __name__ == "__main__":
    main()
