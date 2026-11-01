# task: Write a script that builds a list of the first 30 Fibonacci numbers and prints every third element using extended slicing.
from typing import List


def fibonacci_numbers(count: int) -> List[int]:
    """Return the first `count` Fibonacci numbers, starting with 0, 1."""
    fibs: List[int] = []
    a, b = 0, 1
    for _ in range(count):
        fibs.append(a)
        a, b = b, a + b
    return fibs


def main() -> None:
    fibs: List[int] = fibonacci_numbers(30)
    every_third: List[int] = fibs[::3]
    print("Every third Fibonacci number (indices 0, 3, 6, ...):")
    print(every_third)


if __name__ == "__main__":
    main()
