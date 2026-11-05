MAXV: int = 9223372036854775807
MINV: int = -9223372036854775808


def quo(a: int, b: int) -> int:
    return a // b


def main() -> None:
    print(quo(MAXV, 3))
    print(quo(MINV, 3))
    print(quo(-7, 2))
    print(quo(MINV, -1))


main()
