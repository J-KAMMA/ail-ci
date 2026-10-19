from typing import List


def insertion_sort_count_shifts(values: List[int]) -> tuple[List[int], int]:
    """Return a sorted copy of values and the number of element shifts performed."""
    arr = list(values)
    shifts = 0
    for i in range(1, len(arr)):
        key = arr[i]
        j = i - 1
        while j >= 0 and arr[j] > key:
            arr[j + 1] = arr[j]
            shifts += 1
            j -= 1
        arr[j + 1] = key
    return arr, shifts


def stable_argsort(values: List[int]) -> List[int]:
    """Return the indices that would sort values, ties broken by original position."""
    return sorted(range(len(values)), key=lambda i: (values[i], i))


def main() -> None:
    import sys

    tokens = sys.stdin.read().split()
    if not tokens:
        return
    n = int(tokens[0])
    values = [int(t) for t in tokens[1:1 + n]]

    sorted_values, shifts = insertion_sort_count_shifts(values)
    indices = stable_argsort(values)

    print(shifts)
    print(" ".join(str(v) for v in sorted_values))
    print(" ".join(str(i) for i in indices))


if __name__ == "__main__":
    main()
