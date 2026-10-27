# task: Generate the first 20 Fibonacci numbers with functools.reduce and print only the even values.
from functools import reduce


def next_fib(seq: list[int], _: int) -> list[int]:
    """Append the next Fibonacci number to the sequence."""
    return seq + [seq[-1] + seq[-2]]


def first_fibonacci(count: int) -> list[int]:
    """Return the first `count` Fibonacci numbers (starting 0, 1) using reduce."""
    if count <= 0:
        return []
    if count == 1:
        return [0]
    return reduce(next_fib, range(count - 2), [0, 1])


def main() -> None:
    fibs: list[int] = first_fibonacci(20)
    even_values: list[int] = [n for n in fibs if n % 2 == 0]
    for value in even_values:
        print(value)


if __name__ == "__main__":
    main()
