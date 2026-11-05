def to_int(value: float) -> int:
    return int(value)


def main() -> None:
    wide: float = float("1e19")
    print(to_int(1e3))
    print(to_int(-2.75))
    print(to_int(float("9000000000000000000")))
    print(to_int(wide))


main()
