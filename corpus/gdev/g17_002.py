# task: Compute the factorials of 1 through 10 using functools.reduce and print them as a list.
import functools
import operator


def factorial(n: int) -> int:
    return functools.reduce(operator.mul, range(1, n + 1), 1)


def main() -> None:
    factorials: list[int] = [factorial(n) for n in range(1, 11)]
    print(factorials)


if __name__ == "__main__":
    main()
