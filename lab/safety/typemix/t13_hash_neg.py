def to_int(text: str) -> int:
    return int(text)


n = to_int("-1")
print("minus_one", hash(-1))
print("minus_two", hash(-2))
print("equal", hash(-1) == hash(-2))
print("text", hash(n) == hash(-2))
print("bool", hash(True) == hash(1))
print("float", hash(1.0) == hash(1))
