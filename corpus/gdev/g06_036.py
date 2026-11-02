# task: Write a script that represents a hardcoded set of intervals as integer sets and computes their overlap count using set intersection.
from itertools import combinations

# Closed integer intervals (start, end), both endpoints inclusive.
INTERVALS: tuple[tuple[int, int], ...] = (
    (1, 5),
    (4, 8),
    (10, 12),
    (7, 9),
    (12, 15),
    (20, 20),
    (3, 6),
)


def interval_to_set(interval: tuple[int, int]) -> set[int]:
    """Convert a closed integer interval into a set of its integer points."""
    start, end = interval
    if start > end:
        raise ValueError(f"invalid interval: start {start} > end {end}")
    return set(range(start, end + 1))


def pairwise_overlaps(
    point_sets: list[set[int]],
) -> list[tuple[int, int, set[int]]]:
    """Return (i, j, shared_points) for every pair of sets with a non-empty intersection."""
    results: list[tuple[int, int, set[int]]] = []
    for (i, a), (j, b) in combinations(enumerate(point_sets), 2):
        shared = a & b
        if shared:
            results.append((i, j, shared))
    return results


def main() -> None:
    point_sets: list[set[int]] = [interval_to_set(iv) for iv in INTERVALS]

    overlaps = pairwise_overlaps(point_sets)

    print("Intervals:")
    for idx, iv in enumerate(INTERVALS):
        print(f"  [{idx}] {iv[0]}..{iv[1]} ({len(point_sets[idx])} points)")

    print("\nOverlapping pairs:")
    for i, j, shared in overlaps:
        print(f"  [{i}] & [{j}] -> {sorted(shared)}")

    overlapping_pair_count = len(overlaps)
    total_shared_points = sum(len(shared) for _, _, shared in overlaps)

    # Points covered by at least two intervals: union of all pairwise intersections.
    multi_covered: set[int] = set()
    for _, _, shared in overlaps:
        multi_covered |= shared

    union_all: set[int] = set().union(*point_sets)

    print("\nSummary:")
    print(f"  Overlapping pairs: {overlapping_pair_count}")
    print(f"  Sum of pairwise shared points: {total_shared_points}")
    print(f"  Points covered by 2+ intervals: {len(multi_covered)}")
    print(f"  Distinct points covered overall: {len(union_all)}")
    print(f"  Multi-covered points (sorted): {sorted(multi_covered)}")


if __name__ == "__main__":
    main()
