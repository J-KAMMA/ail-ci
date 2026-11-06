def to_int(text: str) -> int:
    return int(text)


n = to_int("1")
print("eq", 1 == 1.0)
print("lt", 1 < 1.5)
print("int64_edge", 2 ** 63 - 1 < 2.0 ** 63)
print("text", n == 1.0)
print("big", 2 ** 63 == 2.0 ** 63)
