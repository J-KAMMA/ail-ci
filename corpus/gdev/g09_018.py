# task: Determine whether a subset of a fixed list sums to a target value using DP, and print one such subset if it exists.
from typing import Optional


def find_subset_sum(values: list[int], target: int) -> Optional[list[int]]:
    """
    Return one subset of `values` (as a list, in original order) whose sum
    equals `target`, or None if no such subset exists.

    Assumes non-negative integers in `values` and a non-negative target.
    Uses a 2D boolean DP table: reach[i][s] is True when some subset of the
    first i values sums to s.
    """
    if target < 0 or any(v < 0 for v in values):
        return None

    n: int = len(values)
    reach: list[list[bool]] = [[False] * (target + 1) for _ in range(n + 1)]
    reach[0][0] = True

    for i in range(1, n + 1):
        v: int = values[i - 1]
        for s in range(target + 1):
            if reach[i - 1][s]:
                reach[i][s] = True
            elif s >= v and reach[i - 1][s - v]:
                reach[i][s] = True

    if not reach[n][target]:
        return None

    # Reconstruct one subset by walking back through the table.
    chosen: list[int] = []
    s: int = target
    for i in range(n, 0, -1):
        if reach[i - 1][s]:
            # Item i is not needed; the sum is reachable without it.
            continue
        # Item i must be included to reach sum s.
        chosen.append(values[i - 1])
        s -= values[i - 1]

    chosen.reverse()
    return chosen


def main() -> None:
    values: list[int] = [3, 34, 4, 12, 5, 2, 7, 8, 21, 6]
    targets: list[int] = [9, 30, 100, 0]

    print(f"Values: {values}")
    for target in targets:
        subset: Optional[list[int]] = find_subset_sum(values, target)
        if subset is None:
            print(f"Target {target}: no subset sums to {target}.")
        else:
            total: int = sum(subset)
            assert total == target, "internal error: reconstructed subset has wrong sum"
            print(f"Target {target}: subset {subset} (sum = {total}).")


if __name__ == "__main__":
    main()
