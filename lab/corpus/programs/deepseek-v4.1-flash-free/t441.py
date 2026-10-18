import sys
from functools import reduce
from math import gcd


def main() -> None:
    data = sys.stdin.read().split()
    if not data:
        return
    n = int(data[0])
    nums = list(map(int, data[1:1 + n]))

    product = reduce(lambda a, b: a * b, nums, 1)
    common_gcd = reduce(lambda a, b: gcd(a, b), nums)
    concatenation = reduce(lambda a, b: f"{a}{b}", nums, "")

    print(product)
    print(common_gcd)
    print(concatenation)


if __name__ == "__main__":
    main()
