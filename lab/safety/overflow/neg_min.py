MINV: int = -9223372036854775808


def negate(v: int) -> int:
    return -v


def main() -> None:
    print(negate(5))
    print(negate(-7))
    print(negate(MINV + 1))
    print(negate(MINV))


main()
