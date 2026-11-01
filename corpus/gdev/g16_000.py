# task: Write a generator that yields Fibonacci numbers and print the first 20 of them.
from collections.abc import Iterator


def fibonacci() -> Iterator[int]:
    """Yield Fibonacci numbers starting with 0, 1, 1, 2, 3, ..."""
    a, b = 0, 1
    while True:
        yield a
        a, b = b, a + b


def main() -> None:
    first_twenty = list(zip(range(20), fibonacci()))
    for _, value in first_twenty:
        print(value)


if __name__ == "__main__":
    main()
