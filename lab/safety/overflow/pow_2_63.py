def power(base: int, exp: int) -> int:
    return base ** exp


def main() -> None:
    exponents = [10, 62, 5, 63]
    for e in exponents:
        print(power(2, e))


main()
