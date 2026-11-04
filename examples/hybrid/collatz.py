"""Longest Collatz chain below N.

The hot loop is one annotated top-level function, so an `ail build --cpython` build can run it
as native code while the argument parsing and the printing stay in CPython.
"""
import sys


def longest(limit: int) -> int:
    # A start above the loop range is the "single value" probe mode.  It is also how a value
    # outside int64 reaches this function: the hybrid boundary then calls the original Python
    # function instead of truncating it.
    if limit > 10000000:
        n = limit
        steps = 0
        while n != 1:
            if n % 2 == 0:
                n = n // 2
            else:
                n = n * 3 + 1
            steps += 1
        return steps

    best_start = 1
    best_steps = 0
    start = 1
    while start < limit:
        n = start
        steps = 0
        while n != 1:
            if n % 2 == 0:
                n = n // 2
            else:
                n = n * 3 + 1
            steps += 1
        if steps > best_steps:
            best_steps = steps
            best_start = start
        start += 1
    return best_start


def main():
    limit = 300000
    if len(sys.argv) > 1:
        limit = int(sys.argv[1])
    answer = longest(limit)
    if limit > 10000000:
        print("collatz steps for %d: %d" % (limit, answer))
    else:
        print("longest chain below %d: start %d" % (limit, answer))


main()
