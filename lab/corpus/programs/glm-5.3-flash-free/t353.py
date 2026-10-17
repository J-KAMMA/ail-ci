import sys
from typing import List


def quicksort(arr: List[int]) -> List[int]:
    if len(arr) <= 1:
        return arr[:]
    pivot = arr[len(arr) // 2]
    less = [x for x in arr if x < pivot]
    equal = [x for x in arr if x == pivot]
    greater = [x for x in arr if x > pivot]
    return quicksort(less) + equal + quicksort(greater)


def merge_sort(arr: List[int]) -> List[int]:
    if len(arr) <= 1:
        return arr[:]
    mid = len(arr) // 2
    left = merge_sort(arr[:mid])
    right = merge_sort(arr[mid:])
    return _merge(left, right)


def _merge(left: List[int], right: List[int]) -> List[int]:
    merged: List[int] = []
    i = j = 0
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
    data = sys.stdin.read().split()
    n = int(data[0])
    arr = [int(x) for x in data[1 : 1 + n]]
    expected = sorted(arr)
    qs = quicksort(arr)
    ms = merge_sort(arr)
    if qs != expected or ms != expected:
        raise AssertionError("hand-written sorts do not match sorted()")
    print(" ".join(map(str, expected)))
    print("ok")


if __name__ == "__main__":
    main()
