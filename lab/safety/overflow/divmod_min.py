MAXV: int = 9223372036854775807
MINV: int = -9223372036854775808


def split(a: int, b: int) -> tuple:
    return divmod(a, b)


def main() -> None:
    print(split(MAXV, 3))
    print(split(MINV, 3))
    print(split(-7, 2))
    print(split(MINV, -1))


main()
