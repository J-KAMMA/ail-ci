import sys
from bisect import bisect_right


def longest_non_decreasing(nums: list[int]) -> int:
    tails: list[int] = []
    for x in nums:
        pos = bisect_right(tails, x)
        if pos == len(tails):
            tails.append(x)
        else:
            tails[pos] = x
    return len(tails)


def longest_bitonic(nums: list[int]) -> int:
    n = len(nums)
    if n == 0:
        return 0

    inc = [1] * n
    for i in range(n):
        for j in range(i):
            if nums[j] < nums[i] and inc[j] + 1 > inc[i]:
                inc[i] = inc[j] + 1

    dec = [1] * n
    for i in range(n - 1, -1, -1):
        for j in range(i + 1, n):
            if nums[j] < nums[i] and dec[j] + 1 > dec[i]:
                dec[i] = dec[j] + 1

    return max(inc[i] + dec[i] - 1 for i in range(n))


def main() -> None:
    nums = [int(tok) for tok in sys.stdin.read().split()]
    print(longest_non_decreasing(nums), longest_bitonic(nums))


if __name__ == "__main__":
    main()
