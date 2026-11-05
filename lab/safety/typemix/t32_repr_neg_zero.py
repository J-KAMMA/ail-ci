def to_float(text: str) -> float:
    return float(text)


v = to_float("-0.0")
print("repr_neg", repr(-0.0))
print("repr_pos", repr(0.0))
print("str_neg", str(-0.0))
print("text", repr(v))
print("repr_big", repr(1e16))
