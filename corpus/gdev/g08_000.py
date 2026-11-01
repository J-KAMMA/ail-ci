# task: Write a recursive function that computes the nth Fibonacci number with memoization and print fib(90).
from functools import lru_cache


@lru_cache(maxsize=None)
def fib(n: int) -> int:
    """Return the nth Fibonacci number (F(0)=0, F(1)=1) using recursion with memoization."""
    if n < 0:
        raise ValueError("n must be non-negative")
    if n < 2:
        return n
    return fib(n - 1) + fib(n - 2)


def main() -> None:
    print(fib(90))


if __name__ == "__main__":
    main()
