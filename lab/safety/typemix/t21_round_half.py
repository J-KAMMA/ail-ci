def to_float(text: str) -> float:
    return float(text)


v = to_float("2.5")
print("literal", round(2.5))
print("negative", round(-0.5))
print("three", round(3.5))
print("text", round(v))
print("digits", round(2.675, 2))
