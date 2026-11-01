# task: Use functools.lru_cache to memoize a recursive Collatz step counter and print the longest chain starting below 1000.
from functools import lru_cache


@lru_cache(maxsize=None)
def collatz_steps(n: int) -> int:
    """Return the number of Collatz steps needed to reach 1 from n (memoized)."""
    if n <= 1:
        return 0
    next_n = n // 2 if n % 2 == 0 else 3 * n + 1
    return 1 + collatz_steps(next_n)


def main() -> None:
    best_start = 1
    best_steps = collatz_steps(1)
    for start in range(2, 1000):
        steps = collatz_steps(start)
        if steps > best_steps:
            best_start = start
            best_steps = steps
    print(
        f"Longest chain starting below 1000: start={best_start}, "
        f"steps={best_steps}, terms={best_steps + 1}"
    )


if __name__ == "__main__":
    main()
