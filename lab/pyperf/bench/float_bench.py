"""Float bench: a long chain of libm calls and double arithmetic.

Each step combines sqrt, sin, cos, exp and log of values built from the loop
index, and the running total is printed with nine decimals.  Nothing here is
integer: the whole cost is floating-point work and library calls.
"""
import sys
import math


def kernel(n):
    acc = 0.0
    i = 0
    while i < n:
        x = i * 0.0001
        y = x + 1.0
        acc += math.sqrt(y) * 0.5
        acc += math.sin(x) * math.cos(x * 0.5)
        acc -= math.exp(-x * 0.25)
        acc += math.log(y + 0.5)
        if i % 7 == 0:
            acc += math.sqrt(math.fabs(math.sin(x) * math.cos(y)))
        i += 1
    return acc


def main():
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 5000000
    print("%.9f" % kernel(n))
    print("%.9f" % kernel(n // 2))


main()
