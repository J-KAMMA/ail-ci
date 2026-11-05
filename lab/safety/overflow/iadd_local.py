def grow(n: int) -> int:
    total: int = 1
    for i in range(n):
        total += total
    return total


def main() -> None:
    print(grow(4))
    print(grow(62))
    print(grow(1))
    print(grow(64))


main()
