def to_float(text: str) -> float:
    return float(text)


v = to_float("3.9")
print("int_pos", int(3.9))
print("int_neg", int(-3.9))
print("int_true", int(True))
print("float_true", float(True))
print("text", int(v))
