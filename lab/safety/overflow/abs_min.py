MINV: int = -9223372036854775808


def absolute(v: int) -> int:
    return abs(v)


def main() -> None:
    print(absolute(-5))
    print(absolute(7))
    print(absolute(MINV + 1))
    print(absolute(MINV))


main()
