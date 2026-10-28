# task: Find the maximum product of a contiguous subarray in a fixed list of integers and print it.
from typing import Sequence


def max_product_subarray(nums: Sequence[int]) -> int:
    """Return the maximum product of a contiguous non-empty subarray."""
    if not nums:
        raise ValueError("nums must be non-empty")

    best: int = nums[0]
    cur_max: int = nums[0]
    cur_min: int = nums[0]

    for x in nums[1:]:
        candidates = (x, cur_max * x, cur_min * x)
        cur_max = max(candidates)
        cur_min = min(candidates)
        best = max(best, cur_max)

    return best


def main() -> None:
    data: list[int] = [2, 3, -2, 4, -1, 0, -5, 6, -3, 2, -2]
    result: int = max_product_subarray(data)
    print(f"Maximum product of a contiguous subarray: {result}")


if __name__ == "__main__":
    main()
