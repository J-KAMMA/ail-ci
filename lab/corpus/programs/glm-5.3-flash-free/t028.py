import sys
from math import isqrt


def is_perfect_square(x: int) -> bool:
    r = isqrt(x)
    return r * r == x


def main() -> None:
    data = sys.stdin.read().split()
    n = int(data[0])
    nums = [int(t) for t in data[1:1 + n]]
    squares = [x for x in nums if is_perfect_square(x)]
    print(len(squares))
    print(max(squares) if squares else "none")


if __name__ == "__main__":
    main()
