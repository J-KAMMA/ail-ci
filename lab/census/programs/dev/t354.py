import sys


def heap_sort(items: list[int]) -> list[int]:
    """Sort a copy of items using a hand-written max-heap sort."""
    a = list(items)
    n = len(a)

    def sift_down(start: int, end: int) -> None:
        root = start
        while True:
            child = 2 * root + 1
            if child >= end:
                break
            if child + 1 < end and a[child] < a[child + 1]:
                child += 1
            if a[root] < a[child]:
                a[root], a[child] = a[child], a[root]
                root = child
            else:
                break

    # Build max-heap.
    for start in range(n // 2 - 1, -1, -1):
        sift_down(start, n)

    # Repeatedly move the maximum to the end.
    for end in range(n - 1, 0, -1):
        a[0], a[end] = a[end], a[0]
        sift_down(0, end)

    return a


def counting_sort_shifted(items: list[int]) -> list[int]:
    """Shift values to be non-negative, counting-sort them, then shift back."""
    if not items:
        return []
    lo = min(items)
    hi = max(items)
    shifted_max = hi - lo
    counts = [0] * (shifted_max + 1)
    for x in items:
        counts[x - lo] += 1

    result: list[int] = []
    for shifted_value, count in enumerate(counts):
        if count:
            result.extend([shifted_value + lo] * count)
    return result


def bubble_sort_swaps(items: list[int]) -> int:
    """Count the number of swaps bubble sort performs on a copy of items."""
    a = list(items)
    n = len(a)
    swaps = 0
    for i in range(n):
        swapped = False
        for j in range(n - 1 - i):
            if a[j] > a[j + 1]:
                a[j], a[j + 1] = a[j + 1], a[j]
                swaps += 1
                swapped = True
        if not swapped:
            break
    return swaps


def main() -> None:
    data = sys.stdin.read().split()
    if not data:
        return
    n = int(data[0])
    values = [int(tok) for tok in data[1:1 + n]]

    sorted_by_heap = heap_sort(values)
    sorted_by_counting = counting_sort_shifted(values)
    # Both methods must agree; the heap sort result is the one reported.
    assert sorted_by_heap == sorted_by_counting

    swaps = bubble_sort_swaps(values)

    print(" ".join(str(v) for v in sorted_by_heap))
    print(swaps)


if __name__ == "__main__":
    main()
