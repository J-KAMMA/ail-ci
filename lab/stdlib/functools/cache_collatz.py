"""Collatz lengths using functools.cache, a recursive cache shared by many queries."""
from functools import cache


@cache
def steps(n: int) -> int:
    if n == 1:
        return 0
    if n % 2 == 0:
        return 1 + steps(n // 2)
    return 1 + steps(3 * n + 1)


def longest(limit: int) -> int:
    best = 1
    best_len = steps(1)
    for n in range(2, limit + 1):
        length = steps(n)
        if length > best_len:
            best = n
            best_len = length
    return best


def main() -> None:
    for n in (1, 2, 3, 6, 7, 27):
        print(n, steps(n))
    print("longest", longest(1000), steps(longest(1000)))
    info = steps.cache_info()
    print("hits", info.hits, "misses", info.misses, "size", info.currsize)
    print("repeat", steps(27), steps(27))
    print("hits", steps.cache_info().hits)


main()
