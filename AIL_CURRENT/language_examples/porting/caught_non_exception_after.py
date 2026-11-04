def parse(text: str) -> int:
    try:
        return int(text)
    except ValueError:
        return 0


print(parse("12"))
