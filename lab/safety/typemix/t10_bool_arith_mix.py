def to_bool(text: str) -> bool:
    return text == "yes"


flag = to_bool("yes")
print("plus_float", True + 1.5)
print("times_float", True * 2.0)
print("minus", True - 1)
print("text", flag + 0.5)
print("compare", True == 1, True == 1.0)
