def parse(text: str) -> int:
    return int(text)


print("prefix", parse("42"))
print("negative", parse("-7"))
print("next", parse("x"))
