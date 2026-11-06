# task: Use itertools.tee to split a Fibonacci generator into two independent iterators and print the first ten values from each along with their sums.
from collections.abc import Iterator
from itertools import islice, tee


def fibonacci() -> Iterator[int]:
    """Yield the Fibonacci sequence starting at 0, 1, 1, 2, ..."""
    a, b = 0, 1
    while True:
        yield a
        a, b = b, a + b


def main() -> None:
    left, right = tee(fibonacci(), 2)

    first_values: list[int] = list(islice(left, 10))
    second_values: list[int] = list(islice(right, 10))

    print("First iterator: ", first_values)
    print("Second iterator:", second_values)
    print("Sum of first iterator values:  ", sum(first_values))
    print("Sum of second iterator values: ", sum(second_values))

    pairwise_sums: list[int] = [x + y for x, y in zip(first_values, second_values)]
    print("Element-wise sums:", pairwise_sums)
    print("Total of element-wise sums:", sum(pairwise_sums))


if __name__ == "__main__":
    main()
