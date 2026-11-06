def inner(n: int) -> int:
    m = n * 2
    return m + 1


def middle(n: int) -> int:
    x = inner(n)
    return x * 3


def outer(n: int) -> int:
    y = middle(n)
    return y - 4


def main() -> None:
    r = outer(5)
    print(r)


main()
