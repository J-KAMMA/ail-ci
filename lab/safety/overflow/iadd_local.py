def grow(n: int) -> int:
    return 1 << n


def add_local(steps: int) -> int:
    total: int = 3
    for i in range(steps):
        total += total
    return total


def main() -> None:
    print(grow(4))
    print(add_local(4))
    base: int = 1
    for i in range(4):
        base *= 3
    print(base)
    for i in range(40):
        base *= 3
    print(base)


main()
