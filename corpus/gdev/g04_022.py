# task: Find the first and last occurrence of a duplicate target value in a fixed sorted list using two binary searches and print both indices.
from bisect import bisect_left, bisect_right


def find_first_last(sorted_values: list[int], target: int) -> tuple[int, int] | None:
    """Return (first_index, last_index) of target using two binary searches, or None if absent."""
    first = bisect_left(sorted_values, target)
    if first == len(sorted_values) or sorted_values[first] != target:
        return None
    last = bisect_right(sorted_values, target) - 1
    return first, last


def main() -> None:
    data: list[int] = [1, 2, 4, 4, 4, 4, 7, 9, 9, 12, 15, 18, 21]
    target: int = 4

    result = find_first_last(data, target)
    if result is None:
        print(f"Target {target} not found in the list.")
    else:
        first, last = result
        print(f"Target {target}: first occurrence at index {first}")
        print(f"Target {target}: last occurrence at index {last}")


if __name__ == "__main__":
    main()
