def to_float(text: str) -> float:
    return float(text)


v = to_float("1.0")
print("one", str(1.0))
print("big", str(1e16))
print("small", str(1e-5))
print("tenth", str(0.1))
print("text", str(v))
