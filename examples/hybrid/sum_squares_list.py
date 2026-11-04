"""Sum of squares over a list[float] parameter.

The hybrid produces no unit for a `list[float]` parameter, so `sum_squares` runs in CPython;
the program still runs and its output equals CPython's.  Python does the list construction and
the formatting, and the whole loop stays interpreted.
"""
import sys


def sum_squares(xs: list[float]) -> float:
    total = 0.0
    for x in xs:
        total += x * x
    return total


def main():
    size = 2000000
    if len(sys.argv) > 1:
        size = int(sys.argv[1])
    xs = [i * 0.5 for i in range(size)]
    print("count %d" % len(xs))
    print("sum %.1f" % sum_squares(xs))


main()
