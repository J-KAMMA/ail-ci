import math
from typing import Tuple


def describe(n: int) -> Tuple[int, bool]:
    root = math.isqrt(n)
    return root, root * root == n


def main() -> None:
    import sys

    data = sys.stdin.read().split()
    a = int(data[0])
    b = int(data[1])

    root_a, square_a = describe(a)
    root_b, square_b = describe(b)

    print(f"isqrt(a) = {root_a}, perfect square: {square_a}")
    print(f"isqrt(b) = {root_b}, perfect square: {square_b}")


if __name__ == "__main__":
    main()
