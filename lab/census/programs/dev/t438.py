from collections.abc import Generator
from itertools import islice


def fibonacci() -> Generator[int, None, None]:
    """Yield the Fibonacci numbers 0, 1, 1, 2, 3, 5, ... indefinitely."""
    a, b = 0, 1
    while True:
        yield a
        a, b = b, a + b


def main() -> None:
    n = int(input().strip())

    first_n = list(islice(fibonacci(), n))
    print(" ".join(str(x) for x in first_n))

    for value in fibonacci():
        if value > 10**6:
            print(value)
            break


if __name__ == "__main__":
    main()
