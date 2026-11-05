def parse(text: str) -> int:
    return int(text)


print("prefix", parse("0"))
print("spaces", parse(" 12 "))
print("next", parse(""))
