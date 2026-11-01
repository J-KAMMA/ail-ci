"""Order totals with functools.reduce, including the initializer form and the empty case."""
import functools
from functools import reduce


def main() -> None:
    orders = [120, 340, 75, 500, 210]
    total = reduce(lambda a, b: a + b, orders)
    with_tax = reduce(lambda a, b: a + b, orders, 0)
    print("total", total, with_tax)

    print("max", reduce(lambda a, b: a if a > b else b, orders))
    print("min", reduce(lambda a, b: a if a < b else b, orders, orders[0]))
    print("digits", reduce(lambda a, b: a * b, [1, 2, 3, 4, 5], 1))
    print("empty", reduce(lambda a, b: a + b, [], 100))
    print("words", reduce(lambda a, b: a + "-" + b, ["a", "b", "c"]))

    empty = []
    try:
        reduce(lambda a, b: a + b, empty)
    except TypeError as exc:
        print("error", exc)

    summed = functools.reduce(lambda a, b: a + b, [4, 5, 6], 7)
    print("dotted", summed)


main()
