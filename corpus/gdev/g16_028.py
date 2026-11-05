# task: Write a generator that yields the running average of a fixed sequence of numbers and print each value rounded to two decimals.
from collections.abc import Iterable, Iterator


def running_average(numbers: Iterable[float]) -> Iterator[float]:
    """Yield the running average of the numbers as they are consumed."""
    total: float = 0.0
    count: int = 0
    for value in numbers:
        total += value
        count += 1
        yield total / count


def main() -> None:
    sequence: list[float] = [3, 1, 4, 1, 5, 9, 2, 6, 5, 3]
    for average in running_average(sequence):
        print(f"{average:.2f}")


if __name__ == "__main__":
    main()
