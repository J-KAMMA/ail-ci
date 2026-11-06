def to_str(text: str) -> str:
    return text


s = to_str("1_0")
print("underscore", float("1_0"))
print("spaces", float(" 2.5 "))
print("exp", float("1e3"))
print("text", float(s))
print("negative", float("-0.5"))
