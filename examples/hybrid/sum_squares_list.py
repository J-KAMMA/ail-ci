"""Sum of squares over a list[float] parameter.

Since obs3 the hybrid passes a `list[float]` parameter as the clone's `ail_flist`, so
`sum_squares` is native (before, it had no unit and ran in CPython).  Python does the list
construction and the formatting; the output equals CPython's.
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
