# expect: flip=general head=typed main=typed
def flip(xs: list[int]) -> list[int]:
    xs.reverse()
    return xs


def head(xs: list[int]) -> int:
    return xs[0]


def main() -> None:
    print(head([1, 2, 3]))


main()
