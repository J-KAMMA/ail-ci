# task: Implement shell sort with the Knuth gap sequence on a fixed list and print the array after each gap pass.
from typing import List


def knuth_gaps(n: int) -> List[int]:
    """Return the Knuth gap sequence (1, 4, 13, 40, ...) suitable for a list of length n, in ascending order."""
    gaps: List[int] = []
    h = 1
    while h <= n // 3:
        gaps.append(h)
        h = 3 * h + 1
    return gaps


def gapped_insertion_sort(items: List[int], gap: int) -> None:
    """Sort each subsequence of elements spaced `gap` apart using insertion sort, in place."""
    n = len(items)
    for i in range(gap, n):
        temp = items[i]
        j = i
        while j >= gap and items[j - gap] > temp:
            items[j] = items[j - gap]
            j -= gap
        items[j] = temp


def shell_sort(items: List[int]) -> None:
    """Shell sort using the Knuth gap sequence, printing the array after each gap pass."""
    gaps = knuth_gaps(len(items))
    for gap in reversed(gaps):
        gapped_insertion_sort(items, gap)
        print(f"after gap {gap:>2}: {items}")


def main() -> None:
    data: List[int] = [23, 5, 81, 12, 7, 44, 3, 19, 60, 2, 37, 15, 58, 29]
    print(f"initial:        {data}")
    print(f"gap sequence:   {knuth_gaps(len(data))[::-1]}")
    shell_sort(data)
    print(f"sorted:         {data}")


if __name__ == "__main__":
    main()
