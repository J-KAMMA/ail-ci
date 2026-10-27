# task: Check whether a hardcoded list is sorted using a single pass and print the index of the first out-of-order pair if one exists.
from collections.abc import Sequence


def find_first_out_of_order(values: Sequence[int]) -> int | None:
    """Return the index i of the first pair (values[i], values[i+1]) with
    values[i] > values[i+1], or None if the sequence is sorted.
    Performs a single left-to-right pass."""
    for i in range(len(values) - 1):
        if values[i] > values[i + 1]:
            return i
    return None


def main() -> None:
    data: list[int] = [1, 3, 5, 7, 6, 8, 10, 2, 4]

    index = find_first_out_of_order(data)
    if index is None:
        print("The list is sorted.")
    else:
        print(f"First out-of-order pair starts at index {index}: "
              f"data[{index}]={data[index]} > data[{index + 1}]={data[index + 1]}")
        print(f"Index: {index}")


if __name__ == "__main__":
    main()
