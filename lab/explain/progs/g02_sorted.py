# expect: ordered=general total=typed main=typed
def ordered(xs: list[int]) -> list[int]:
    return sorted(xs)


def total(xs: list[int]) -> int:
    t: int = 0
    for x in xs:
        t = t + x
    return t


def main() -> None:
    print(total([3, 1, 2]))


main()
