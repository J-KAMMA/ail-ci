# task: Find the intersection of two fixed sorted lists using a two-pointer technique and print the common elements.
from typing import List


def intersect_sorted(a: List[int], b: List[int]) -> List[int]:
    """Return the common elements of two sorted lists using two pointers.

    Duplicates are preserved according to their multiplicity in both lists
    (the k-th occurrence in a matches the k-th occurrence in b).
    """
    result: List[int] = []
    i, j = 0, 0
    while i < len(a) and j < len(b):
        if a[i] == b[j]:
            result.append(a[i])
            i += 1
            j += 1
        elif a[i] < b[j]:
            i += 1
        else:
            j += 1
    return result


def main() -> None:
    list_a: List[int] = [1, 2, 2, 3, 4, 6, 7, 9, 11, 15]
    list_b: List[int] = [2, 2, 3, 5, 6, 8, 9, 10, 15, 20]

    common = intersect_sorted(list_a, list_b)

    print("List A:", list_a)
    print("List B:", list_b)
    print("Common elements:", common)


if __name__ == "__main__":
    main()
