def to_float(text: str) -> float:
    return float(text)


v = to_float("2")
print("literal", divmod(-7.5, 2))
print("float_left", divmod(7, 2.0))
print("both_neg", divmod(-7, -2.0))
print("text", divmod(-7.5, v))
print("positive", divmod(7.5, 2))
