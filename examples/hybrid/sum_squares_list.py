"""Sum of squares over a list[float] parameter.

The list is copied into the native call, the loop runs as typed C, and Python does the list
construction and the formatting.
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
