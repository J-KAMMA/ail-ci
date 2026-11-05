MAXV: int = 9223372036854775807
MINV: int = -9223372036854775808


def add(a: int, b: int) -> int:
    return a + b


def main() -> None:
    print(add(MINV + 5, -3))
    print(add(MAXV - 5, 3))
    print(add(0, 0))
    print(add(MAXV, 1))


main()
