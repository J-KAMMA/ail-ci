# expect: add=typed mul=typed main=typed
def add(a: int, b: int) -> int:
    return a + b


def mul(a: int, b: int) -> int:
    return a * b


def main() -> None:
    x: int = add(2, 3)
    print(mul(x, 4))


main()
