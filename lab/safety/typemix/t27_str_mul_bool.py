def to_bool(text: str) -> bool:
    return text == "yes"


flag = to_bool("yes")
print("literal", "a" * True)
print("false", "ab" * False)
print("expr", "-" * (True + True))
print("text", "x" * flag)
print("int", "hi" * 2)
