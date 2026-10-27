# task: Use itertools.takewhile with an infinite powers-of-two generator to print all powers of two below 10000.
import itertools
from collections.abc import Iterator


def powers_of_two() -> Iterator[int]:
    """Yield 1, 2, 4, 8, ... indefinitely."""
    power = 1
    while True:
        yield power
        power *= 2


def main() -> None:
    for value in itertools.takewhile(lambda x: x < 10000, powers_of_two()):
        print(value)


if __name__ == "__main__":
    main()
