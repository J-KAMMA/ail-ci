# expect: pair=typed first=typed main=typed
def pair(x: int) -> tuple[int, int]:
    return (x, x + 1)


def first(t: tuple[int, int]) -> int:
    return t[0]


def main() -> None:
    print(first(pair(7)))


main()
