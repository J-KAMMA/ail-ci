"""A typed cache that keeps 1, 1.0 and True apart."""
from functools import lru_cache


@lru_cache(maxsize=8, typed=True)
def describe(value):
    return type(value).__name__ + ":" + str(value)


@lru_cache(maxsize=8)
def untyped(value):
    return str(value)


def main() -> None:
    print(describe(1))
    print(describe(1.0))
    print(describe(True))
    print(describe(1))
    info = describe.cache_info()
    print("typed", info.hits, info.misses, info.maxsize, info.currsize)

    print(untyped(1))
    print(untyped(1.0))
    print(untyped(True))
    info = untyped.cache_info()
    print("untyped", info.hits, info.misses, info.maxsize, info.currsize)

    describe.cache_clear()
    print(describe(2), describe(2))
    print(describe.cache_info().hits, describe.cache_info().misses)


main()
