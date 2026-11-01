# task: Compute the sum of squares of odd numbers from 1 to 50 using a pipeline of filter, map, and reduce.
from functools import reduce
from typing import Iterable


def numbers(limit: int) -> Iterable[int]:
    return range(1, limit + 1)


def is_odd(n: int) -> bool:
    return n % 2 == 1


def square(n: int) -> int:
    return n * n


def add(acc: int, x: int) -> int:
    return acc + x


def main() -> None:
    odd_squares = map(square, filter(is_odd, numbers(50)))
    total = reduce(add, odd_squares, 0)
    print(total)


if __name__ == "__main__":
    main()
