import sys


def longest_strictly_increasing_run(nums: list[int]) -> int:
    if not nums:
        return 0
    best = current = 1
    for i in range(1, len(nums)):
        if nums[i] > nums[i - 1]:
            current += 1
        else:
            current = 1
        if current > best:
            best = current
    return best


def main() -> None:
    data = sys.stdin.read().split()
    if not data:
        return
    n = int(data[0])
    nums = [int(x) for x in data[1:1 + n]]
    print(longest_strictly_increasing_run(nums))


if __name__ == "__main__":
    main()
