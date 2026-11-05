def to_float(text: str) -> float:
    return float(text)


print("small", int(3.9))
print("negative", int(-2.5))
print("text", int(to_float("1e10")))
value = to_float("1e300")
print("huge", int(value))
