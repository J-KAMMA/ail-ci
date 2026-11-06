# expect: tail=general first=typed main=typed
def tail(xs: list[int]) -> list[int]:
    ys: list[int] = xs[1:]
    return ys


def first(xs: list[int]) -> int:
    return xs[0]


def main() -> None:
    print(first([1, 2, 3]))


main()
