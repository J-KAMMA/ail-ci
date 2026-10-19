import sys


def main() -> None:
    data: list[str] = sys.stdin.read().split()
    if not data:
        return

    n: int = int(data[0])
    nums: list[int] = list(map(int, data[1:1 + n]))

    total: int = sum(x for x in nums)

    weighted: int = sum(i * x for i, x in enumerate(nums, start=1))

    abs_diff_sum: int = sum(abs(b - a) for a, b in zip(nums, nums[1:]))

    squares_sum: int = sum(map(lambda x: x * x, nums))

    even_count: int = len(list(filter(lambda x: x % 2 == 0, nums)))

    any_multiple_of_7: bool = any(x % 7 == 0 for x in nums)

    all_positive: bool = all(x > 0 for x in nums)

    print(f"Sum: {total}")
    print(f"Index-weighted sum (enumerate, start=1): {weighted}")
    print(f"Sum of absolute consecutive differences (zip): {abs_diff_sum}")
    print(f"Sum of squares (map): {squares_sum}")
    print(f"Even count (filter): {even_count}")
    print(f"Any multiple of 7: {any_multiple_of_7}")
    print(f"All positive: {all_positive}")


if __name__ == "__main__":
    main()
