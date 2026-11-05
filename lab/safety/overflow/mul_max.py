MAXV: int = 9223372036854775807
MINV: int = -9223372036854775808


def mul(a: int, b: int) -> int:
    return a * b


def main() -> None:
    print(mul(MINV // 2, 2))
    print(mul(3, 4))
    print(mul(-3, 4))
    print(mul(MAXV, 2))


main()
