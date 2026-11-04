"""Count primes below N by trial division.

The hybrid refuses `%` with a non-constant divisor (it can raise ZeroDivisionError), so this
program does the divisibility test by repeated subtraction instead.  The result is the same and
the loop is still integer only.
"""
import sys


def prime_count(limit: int) -> int:
    count = 0
    n = 2
    while n < limit:
        d = 2
        composite = 0
        while d * d <= n:
            rest = n
            while rest >= d:
                rest -= d
            if rest == 0:
                composite = 1
                d = n
            d += 1
        if composite == 0:
            count += 1
        n += 1
    return count


def main():
    limit = 10000
    if len(sys.argv) > 1:
        limit = int(sys.argv[1])
    print("primes below %d: %d" % (limit, prime_count(limit)))


main()
