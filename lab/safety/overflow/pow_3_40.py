def power(base: int, exp: int) -> int:
    return pow(base, exp)


def main() -> None:
    exponents = [4, 39, 0, 40]
    for e in exponents:
        print(power(3, e))


main()
