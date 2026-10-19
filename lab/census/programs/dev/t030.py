import sys


def main() -> None:
    data: list[str] = sys.stdin.read().split()
    n: int = int(data[0])
    nums: list[int] = sorted(int(x) for x in data[1:1 + n])

    best_diff: int = nums[1] - nums[0]
    best_a: int = nums[0]
    best_b: int = nums[1]

    for i in range(1, len(nums) - 1):
        diff: int = nums[i + 1] - nums[i]
        if diff < best_diff:
            best_diff = diff
            best_a = nums[i]
            best_b = nums[i + 1]

    print(best_a, best_b, best_diff)


if __name__ == "__main__":
    main()
