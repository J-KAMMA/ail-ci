def to_str(text: str) -> str:
    return text


s = to_str(" 12 ")
print("spaces", int(" 12 "))
print("negative", int("-12"))
print("text", int(s))
print("next", int("3.0"))
