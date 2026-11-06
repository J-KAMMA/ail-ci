# expect: outer=typed main=typed
def outer(n: int) -> int:
    def inner(x: int) -> int:
        return x * 3
    return inner(n) + 1


def main() -> None:
    print(outer(4))


main()
