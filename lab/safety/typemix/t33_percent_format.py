def to_float(text: str) -> float:
    return float(text)


v = to_float("3.9")
print("int_float", "%d" % 3.9)
print("int_bool", "%d" % True)
print("str_bool", "%s" % True)
print("float", "%f" % 2)
print("text", "%d" % v)
print("percent", "%s" % 1.0)
