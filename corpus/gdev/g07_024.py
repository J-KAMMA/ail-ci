# task: Write a script that deletes elements at specified indices from a hardcoded list, processing the indices in descending order, and prints the result.
from typing import List


def delete_indices_descending(items: List[int], indices: List[int]) -> List[int]:
    """Return a new list with elements at the given indices removed.

    Indices are processed in descending order so that earlier deletions
    do not shift the positions of indices still to be removed.
    Duplicate and out-of-range indices are ignored safely.
    """
    result = list(items)
    for index in sorted(set(indices), reverse=True):
        if 0 <= index < len(result):
            del result[index]
    return result


def main() -> None:
    data: List[int] = [10, 20, 30, 40, 50, 60, 70, 80, 90]
    indices_to_delete: List[int] = [1, 3, 3, 7, 0, 42]

    print("Original list:", data)
    print("Indices to delete:", indices_to_delete)

    result = delete_indices_descending(data, indices_to_delete)

    print("Resulting list:", result)


if __name__ == "__main__":
    main()
