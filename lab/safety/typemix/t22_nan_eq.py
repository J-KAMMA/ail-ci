def to_float(text: str) -> float:
    return float(text)


nan = to_float("nan")
print("eq", float("nan") == float("nan"))
print("ne", float("nan") != float("nan"))
print("lt", float("nan") < float("nan"))
print("text_eq", nan == nan)
print("is", nan == float("nan"))
