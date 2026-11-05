def to_float(text: str) -> float:
    return float(text)


v = to_float("2.0")
print("literal", -7 % 2.0)
print("float_left", 7 % -2.0)
print("fraction", -7.5 % 2)
print("text", -7 % v)
print("positive", 7 % 2.0)
