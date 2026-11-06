def to_float(text: str) -> float:
    return float(text)


v = to_float("2.0")
print("literal", -7 // 2.0)
print("float_left", -7.0 // 2)
print("both_neg", -7 // -2.0)
print("text", -7 // v)
print("positive", 7 // 2.0)
