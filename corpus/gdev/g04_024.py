# task: Search for a value in a fixed rotated sorted array using modified binary search and print the index found or -1.
def search_rotated(nums: list[int], target: int) -> int:
    """Return the index of target in a rotated sorted array, or -1 if absent.

    Uses a modified binary search: at each step, at least one half of the
    current window is sorted, so we check whether the target lies within
    that sorted half and narrow the window accordingly.
    """
    lo, hi = 0, len(nums) - 1
    while lo <= hi:
        mid = (lo + hi) // 2
        if nums[mid] == target:
            return mid
        if nums[lo] <= nums[mid]:
            # Left half [lo..mid] is sorted.
            if nums[lo] <= target < nums[mid]:
                hi = mid - 1
            else:
                lo = mid + 1
        else:
            # Right half [mid..hi] is sorted.
            if nums[mid] < target <= nums[hi]:
                lo = mid + 1
            else:
                hi = mid - 1
    return -1


def main() -> None:
    # A fixed rotated sorted array (originally [0, 1, 2, 4, 5, 6, 7], rotated).
    array: list[int] = [4, 5, 6, 7, 0, 1, 2]
    targets: list[int] = [0, 3, 4, 7, 2, 8, -1]

    print(f"array: {array}")
    for target in targets:
        index = search_rotated(array, target)
        print(f"search({target}) -> {index}")


if __name__ == "__main__":
    main()
