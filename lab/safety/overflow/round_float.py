def rounded(value: float) -> int:
    return round(value)


def main() -> None:
    wide: float = float("1e19")
    print(rounded(1.25))
    print(rounded(-2.5))
    print(rounded(float("9000000000000000000")))
    print(rounded(wide))


main()
