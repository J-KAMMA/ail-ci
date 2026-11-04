# task: Find the minimum number of jumps needed to reach the end of a fixed array where each element gives the maximum jump length and print it.
from typing import Sequence


def min_jumps(nums: Sequence[int]) -> int:
    """Return the minimum number of jumps to reach the last index, or -1 if unreachable."""
    n = len(nums)
    if n <= 1:
        return 0

    jumps = 0
    current_end = 0  # furthest index reachable with the current number of jumps
    farthest = 0     # furthest index reachable with one more jump

    for i in range(n - 1):
        farthest = max(farthest, i + nums[i])
        if i == current_end:
            # Must take another jump to go beyond current_end.
            jumps += 1
            current_end = farthest
            if current_end >= n - 1:
                break
            if current_end <= i:
                return -1  # stuck at index i

    return jumps if current_end >= n - 1 else -1


def main() -> None:
    examples: list[list[int]] = [
        [2, 3, 1, 1, 4],
        [2, 3, 0, 1, 4],
        [1, 1, 1, 1],
        [0, 2],
        [5],
        [3, 2, 1, 0, 4],
    ]
    for index, nums in enumerate(examples, start=1):
        result = min_jumps(nums)
        print(f"Example {index}: array={nums} -> minimum jumps = {result}")


if __name__ == "__main__":
    main()
