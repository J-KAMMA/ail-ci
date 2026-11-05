MAXV: int = 9223372036854775807
MINV: int = -9223372036854775808


def rem(a: int, b: int) -> int:
    return a % b


def main() -> None:
    print(rem(MAXV, 3))
    print(rem(MINV, 3))
    print(rem(-7, 2))
    print(rem(MINV, -1))


main()
