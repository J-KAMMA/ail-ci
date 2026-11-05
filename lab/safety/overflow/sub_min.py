MAXV: int = 9223372036854775807
MINV: int = -9223372036854775808


def sub(a: int, b: int) -> int:
    return a - b


def main() -> None:
    print(sub(MINV + 5, 3))
    print(sub(MAXV - 5, 3))
    print(sub(0, 0))
    print(sub(MINV, 1))


main()
