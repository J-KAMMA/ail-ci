def parse(text: str) -> int:
    try:
        return int(text)
    except int:
        return 0


print(parse("12"))
