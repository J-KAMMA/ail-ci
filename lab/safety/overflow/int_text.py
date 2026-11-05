def parse(text: str) -> int:
    return int(text)


def main() -> None:
    digits: str = ""
    for i in range(20):
        digits += "9"
    print(parse("1234567890123456789"))
    print(parse("42"))
    print(parse(digits))


main()
