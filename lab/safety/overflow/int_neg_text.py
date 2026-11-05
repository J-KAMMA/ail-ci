def parse(text: str) -> int:
    return int(text)


def main() -> None:
    source: str = "-922337203685477580"
    text: str = ""
    for i in range(len(source)):
        text += source[i]
    text += "9"
    print(parse(source))
    print(parse("-42"))
    print(parse(text))


main()
