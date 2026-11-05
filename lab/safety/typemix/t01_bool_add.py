def to_int(text: str) -> int:
    return int(text)


def to_bool(text: str) -> bool:
    return text == "yes"


flag = to_bool("yes")
other = to_bool("no")
print("literal", True + True)
print("mixed", True + False)
print("from_text", flag + other)
print("both", flag + flag + True)
print("zero", False + False)
