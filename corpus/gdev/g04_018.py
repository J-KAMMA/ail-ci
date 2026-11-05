# task: Use bisect module functions to find the insertion point for several values in a fixed sorted list and print the results.
import bisect
from typing import Sequence


def describe_insertion(
    sorted_values: Sequence[int], target: int
) -> tuple[int, int, int]:
    """Return (left_index, right_index, count_equal) for a target value."""
    left: int = bisect.bisect_left(sorted_values, target)
    right: int = bisect.bisect_right(sorted_values, target)
    return left, right, right - left


def main() -> None:
    sorted_values: list[int] = [1, 3, 3, 5, 7, 7, 7, 9, 12, 15]
    targets: list[int] = [0, 1, 3, 4, 7, 8, 12, 15, 16]

    print(f"Sorted list: {sorted_values}")
    print(f"{'target':>6} {'left':>5} {'right':>6} {'equal':>6} {'insort':>7}")

    for target in targets:
        left, right, count = describe_insertion(sorted_values, target)

        # Show what insort would produce on a copy, without mutating the original.
        preview: list[int] = sorted_values.copy()
        bisect.insort(preview, target)
        insort_position: int = preview.index(target, left)

        print(
            f"{target:>6} {left:>5} {right:>6} {count:>6} {insort_position:>7}"
        )

    # Demonstrate key-based search with bisect on a list of tuples.
    records: list[tuple[int, str]] = [
        (10, "alpha"),
        (20, "beta"),
        (30, "gamma"),
        (40, "delta"),
    ]
    keys: list[int] = [r[0] for r in records]
    for probe in (5, 20, 25, 45):
        idx: int = bisect.bisect(keys, probe)
        print(f"Key probe {probe}: insert at index {idx}")


if __name__ == "__main__":
    main()
