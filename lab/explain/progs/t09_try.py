# expect: parse=typed main=typed
def parse(s: str) -> int:
    try:
        return int(s)
    except ValueError:
        return -1


def main() -> None:
    print(parse("12"))
    print(parse("nope"))


main()
