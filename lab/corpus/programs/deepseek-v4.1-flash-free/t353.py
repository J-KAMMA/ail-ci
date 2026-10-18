import sys


def quicksort(data: list[int]) -> list[int]:
    if len(data) <= 1:
        return list(data)
    pivot = data[len(data) // 2]
    left = [x for x in data if x < pivot]
    mid = [x for x in data if x == pivot]
    right = [x for x in data if x > pivot]
    return quicksort(left) + mid + quicksort(right)


def merge_sort(data: list[int]) -> list[int]:
    if len(data) <= 1:
        return list(data)
    middle = len(data) // 2
    left = merge_sort(data[:middle])
    right = merge_sort(data[middle:])
    merged: list[int] = []
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
    tokens = sys.stdin.read().split()
    if not tokens:
        return
    n = int(tokens[0])
    values = [int(t) for t in tokens[1:1 + n]]
    expected = sorted(values)
    a = quicksort(values)
    b = merge_sort(values)
    assert a == expected, "quicksort mismatch"
    assert b == expected, "merge sort mismatch"
    print(" ".join(map(str, a)))
    print("ok")


if __name__ == "__main__":
    main()
