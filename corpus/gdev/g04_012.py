# task: Implement comb sort on a fixed list of integers and print the gap value used in each iteration.
from typing import List


def comb_sort(items: List[int]) -> List[int]:
    """Sort a copy of the list using comb sort, printing the gap of each pass."""
    data: List[int] = list(items)
    n: int = len(data)
    gap: int = n
    swapped: bool = True

    while gap > 1 or swapped:
        # Shrink the gap by the conventional factor 1.3 (computed with integers).
        gap = max(1, gap * 10 // 13)
        print(f"gap = {gap}")

        swapped = False
        for i in range(n - gap):
            if data[i] > data[i + gap]:
                data[i], data[i + gap] = data[i + gap], data[i]
                swapped = True

    return data


def main() -> None:
    values: List[int] = [8, 4, 1, 56, 3, -44, 23, -6, 28, 0, 15, -2]
    print(f"original: {values}")
    result: List[int] = comb_sort(values)
    print(f"sorted:   {result}")


if __name__ == "__main__":
    main()
