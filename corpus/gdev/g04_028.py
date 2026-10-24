# task: Find the median of a fixed list of integers without fully sorting it and print the result along with the comparisons made.
from __future__ import annotations


DATA: list[int] = [38, 27, 43, 3, 9, 82, 10, 55, 21, 7, 64, 14, 31]


class ComparisonTracker:
    """Performs and records every comparison made during selection."""

    def __init__(self) -> None:
        self.log: list[tuple[int, int, bool]] = []

    def less(self, a: int, b: int) -> bool:
        result = a < b
        self.log.append((a, b, result))
        return result


def select_kth(values: list[int], k: int, tracker: ComparisonTracker) -> int:
    """Return the k-th smallest (0-based) value using deterministic quickselect.

    Only the partitions needed to locate position k are processed, so the
    whole list is never fully sorted. The input list is not modified.
    """
    items = list(values)
    lo, hi = 0, len(items) - 1
    while True:
        if lo == hi:
            return items[lo]
        mid = (lo + hi) // 2
        pivot = items[mid]
        # Move the pivot to the end of the active range (Lomuto partition).
        items[mid], items[hi] = items[hi], items[mid]
        store = lo
        for i in range(lo, hi):
            if tracker.less(items[i], pivot):
                items[i], items[store] = items[store], items[i]
                store += 1
        items[store], items[hi] = items[hi], items[store]
        if k == store:
            return items[store]
        if k < store:
            hi = store - 1
        else:
            lo = store + 1


def find_median(values: list[int], tracker: ComparisonTracker) -> float:
    """Median of values; averages the two middle elements for even lengths."""
    n = len(values)
    if n % 2 == 1:
        return float(select_kth(values, n // 2, tracker))
    lower = select_kth(values, n // 2 - 1, tracker)
    upper = select_kth(values, n // 2, tracker)
    return (lower + upper) / 2


def main() -> None:
    tracker = ComparisonTracker()
    median = find_median(DATA, tracker)

    print(f"Input ({len(DATA)} values): {DATA}")
    print(f"Median: {median:g}")
    print(f"Comparisons made: {len(tracker.log)}")
    for index, (a, b, result) in enumerate(tracker.log, start=1):
        print(f"  {index:3d}. {a} < {b} -> {result}")

    expected_sorted = sorted(DATA)
    n = len(expected_sorted)
    if n % 2 == 1:
        expected = float(expected_sorted[n // 2])
    else:
        expected = (expected_sorted[n // 2 - 1] + expected_sorted[n // 2]) / 2
    print(f"Verified against sorted(): {expected == median}")


if __name__ == "__main__":
    main()
