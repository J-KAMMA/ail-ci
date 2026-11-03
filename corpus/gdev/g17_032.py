# task: Use functools.lru_cache to count the ways to climb n stairs with steps of 1, 2, or 3 for n up to 30.
from functools import lru_cache


@lru_cache(maxsize=None)
def count_ways(n: int) -> int:
    """Return the number of ways to climb n stairs taking 1, 2, or 3 steps at a time."""
    if n < 0:
        return 0
    if n == 0:
        return 1
    return count_ways(n - 1) + count_ways(n - 2) + count_ways(n - 3)


def main() -> None:
    for n in range(0, 31):
        print(f"{n:2d} stairs: {count_ways(n)} ways")


if __name__ == "__main__":
    main()
