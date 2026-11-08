# task: Find all pairs of integers in a fixed list that sum to a target value using sorting and two pointers and print the pairs.
from typing import List, Tuple


def find_pairs_with_sum(numbers: List[int], target: int) -> List[Tuple[int, int]]:
    """
    Return every distinct pair of values (a, b) with a + b == target.

    The list is sorted first, then two pointers move inward from both ends:
    - If the sum is too small, the left pointer moves right.
    - If the sum is too large, the right pointer moves left.
    - On a match, the pair is recorded and both pointers skip past
      equal values so each distinct pair is reported only once.

    Pairs are returned in ascending order of their smaller element.
    """
    nums = sorted(numbers)
    left = 0
    right = len(nums) - 1
    pairs: List[Tuple[int, int]] = []

    while left < right:
        total = nums[left] + nums[right]
        if total == target:
            left_val = nums[left]
            right_val = nums[right]
            pairs.append((left_val, right_val))
            while left < right and nums[left] == left_val:
                left += 1
            while left < right and nums[right] == right_val:
                right -= 1
        elif total < target:
            left += 1
        else:
            right -= 1

    return pairs


def main() -> None:
    numbers: List[int] = [3, -1, 4, 7, 2, 2, 8, -3, 5, 6, 1, 9, 0, 4]
    target: int = 6

    print(f"Numbers: {numbers}")
    print(f"Target sum: {target}")

    pairs = find_pairs_with_sum(numbers, target)

    if not pairs:
        print("No pairs found.")
    else:
        print(f"Found {len(pairs)} pair(s):")
        for a, b in pairs:
            print(f"  {a} + {b} = {target}")


if __name__ == "__main__":
    main()
