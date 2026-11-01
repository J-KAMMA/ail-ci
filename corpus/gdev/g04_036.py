# task: Determine the majority element in a fixed list using Boyer-Moore voting and verify it by counting occurrences with sorting.
from bisect import bisect_left, bisect_right
from typing import Optional, Sequence, TypeVar

T = TypeVar("T")


def boyer_moore_candidate(items: Sequence[T]) -> Optional[T]:
    """Return the Boyer-Moore voting candidate for the list (may not be a majority)."""
    candidate: Optional[T] = None
    count = 0
    for item in items:
        if count == 0:
            candidate = item
            count = 1
        elif item == candidate:
            count += 1
        else:
            count -= 1
    return candidate


def count_by_sorting(items: Sequence[T], target: T) -> int:
    """Count occurrences of target by sorting a copy and binary-searching the run."""
    ordered = sorted(items)  # type: ignore[type-var]
    lo = bisect_left(ordered, target)  # type: ignore[type-var]
    hi = bisect_right(ordered, target)  # type: ignore[type-var]
    return hi - lo


def find_majority(items: Sequence[T]) -> Optional[T]:
    """Return the majority element (more than half of items), or None if none exists."""
    if not items:
        return None
    candidate = boyer_moore_candidate(items)
    if candidate is None:
        return None
    occurrences = count_by_sorting(items, candidate)
    if occurrences * 2 > len(items):
        return candidate
    return None


def report(label: str, items: Sequence[T]) -> None:
    candidate = boyer_moore_candidate(items)
    print(f"{label}: {list(items)}")
    print(f"  Boyer-Moore candidate: {candidate!r}")
    if candidate is not None:
        occurrences = count_by_sorting(items, candidate)
        print(f"  Occurrences (sorted count): {occurrences} of {len(items)}")
    majority = find_majority(items)
    if majority is not None:
        print(f"  Verified majority element: {majority!r}")
    else:
        print("  No majority element exists.")


def main() -> None:
    fixed_with_majority: list[int] = [2, 7, 2, 3, 2, 2, 5, 2, 7, 2, 2]
    fixed_without_majority: list[int] = [1, 2, 3, 1, 2, 3, 4]

    report("List A", fixed_with_majority)
    print()
    report("List B", fixed_without_majority)


if __name__ == "__main__":
    main()
