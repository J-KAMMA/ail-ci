def to_int(text: str) -> int:
    return int(text)


half = to_int("2")
print("true_div", True / 2)
print("false_div", False / 2)
print("text_div", True / half)
print("floor", True // 2)
print("mod", True % 2)
