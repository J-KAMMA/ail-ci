"""The errors functools raises, caught the way ordinary code catches them."""
from functools import lru_cache, partial, reduce


def combine(a, b, sep="-"):
    return f"{a}{sep}{b}"


@lru_cache(maxsize=4)
def doubled(n):
    return n * 2


def main() -> None:
    try:
        reduce(lambda a, b: a + b, [])
    except TypeError as exc:
        print("reduce", exc)

    try:
        doubled([1, 2])
    except TypeError as exc:
        print("cache", exc)

    join = partial(combine, sep="+")
    print(join("a", "b"))
    print(partial(combine, "x")("y", ":"))
    early = partial(combine, "left", "right")
    print(early(), early("/"))
    print(doubled(3), doubled(3), doubled(4))
    print(doubled.cache_info().hits, doubled.cache_info().misses)


main()
