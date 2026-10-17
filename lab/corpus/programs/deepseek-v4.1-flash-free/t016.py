import sys


def main() -> None:
    data = sys.stdin.read().split()
    if not data:
        return
    n = int(data[0])
    nums = [int(x) for x in data[1:1 + n]]
    maximum = max(nums)
    first_index = nums.index(maximum)
    count = nums.count(maximum)
    print(first_index, count)


if __name__ == "__main__":
    main()
