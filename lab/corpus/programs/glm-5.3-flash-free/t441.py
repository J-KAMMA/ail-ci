import sys
from functools import reduce
from math import gcd


def main() -> None:
    data = sys.stdin.read().split()
    n = int(data[0])
    numbers = [int(x) for x in data[1 : 1 + n]]
    product = reduce(lambda a, b: a * b, numbers)
    overall_gcd = reduce(lambda a, b: gcd(a, b), numbers)
    concatenated = reduce(lambda a, b: a + b, [str(x) for x in numbers])
    print(product)
    print(overall_gcd)
    print(concatenated)


if __name__ == "__main__":
    main()
