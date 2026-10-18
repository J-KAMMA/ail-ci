import sys
from itertools import accumulate


def main() -> None:
    data = sys.stdin.read().split()
    n = int(data[0])
    nums = list(map(int, data[1 : 1 + n]))
    if nums:
        print(*accumulate(nums, max))


if __name__ == "__main__":
    main()
