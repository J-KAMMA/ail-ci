import math
import sys


def is_perfect_square(value: int) -> bool:
    if value < 0:
        return False
    root = math.isqrt(value)
    return root * root == value


def main() -> None:
    data = sys.stdin.read().split()
    if not data:
        return
    n = int(data[0])
    numbers = [int(token) for token in data[1:1 + n]]

    squares = [x for x in numbers if is_perfect_square(x)]
    count = len(squares)
    largest = str(max(squares)) if squares else "none"

    print(count, largest)


if __name__ == "__main__":
    main()
