# task: Memoize Fibonacci numbers in a dictionary, print the first 30 values, and report the final cache size.
from __future__ import annotations


def fib(n: int, cache: dict[int, int]) -> int:
    """Return the n-th Fibonacci number, memoized in `cache`."""
    if n in cache:
        return cache[n]
    if n < 2:
        result = n
    else:
        result = fib(n - 1, cache) + fib(n - 2, cache)
    cache[n] = result
    return result


def main() -> None:
    cache: dict[int, int] = {}
    count = 30

    values: list[int] = [fib(n, cache) for n in range(count)]

    for n, value in enumerate(values):
        print(f"F({n}) = {value}")

    print(f"Final cache size: {len(cache)}")


if __name__ == "__main__":
    main()
