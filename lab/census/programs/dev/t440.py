import sys
from functools import lru_cache


@lru_cache(maxsize=None)
def p(n: int, k: int) -> int:
    """Number of partitions of n into parts of size at most k."""
    if n == 0:
        return 1
    if k == 0:
        return 0
    if k > n:
        return p(n, n)
    return p(n, k - 1) + p(n - k, k)


def main() -> None:
    n = int(sys.stdin.readline().strip())
    value = p(n, n)
    info = p.cache_info()
    print(f"p({n},{n}) = {value}")
    print(f"hits={info.hits} misses={info.misses}")


if __name__ == "__main__":
    main()
