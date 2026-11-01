"""Memoised Fibonacci with functools.lru_cache and its cache statistics."""
from functools import lru_cache


@lru_cache(maxsize=None)
def fib(n: int) -> int:
    if n < 2:
        return n
    return fib(n - 1) + fib(n - 2)


def main() -> None:
    for i in range(0, 16, 3):
        print(i, fib(i))

    info = fib.cache_info()
    print("info", info.hits, info.misses, info.maxsize, info.currsize)

    print("again", fib(12), fib(0), fib(1))
    info = fib.cache_info()
    print("info", info.hits, info.misses, info.maxsize, info.currsize)

    fib.cache_clear()
    print("cleared", fib(10))
    info = fib.cache_info()
    print("info", info.hits, info.misses, info.currsize)


main()
