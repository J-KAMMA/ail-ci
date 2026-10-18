import sys
from functools import lru_cache


@lru_cache(maxsize=None)
def p(n: int, k: int) -> int:
    if n == 0:
        return 1
    if n < 0 or k == 0:
        return 0
    return p(n, k - 1) + p(n - k, k)


def main() -> None:
    n = int(sys.stdin.readline().strip())
    result = p(n, n)
    info = p.cache_info()
    print(result)
    print(info.hits, info.misses)


if __name__ == "__main__":
    main()
