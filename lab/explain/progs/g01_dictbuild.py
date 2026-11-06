# expect: counts=general total=typed main=typed
def counts(n: int) -> dict[str, int]:
    d = {}
    d["n"] = n
    return d


def total(xs: list[int]) -> int:
    t: int = 0
    for x in xs:
        t = t + x
    return t


def main() -> None:
    print(total([3, 1, 2]))


main()
