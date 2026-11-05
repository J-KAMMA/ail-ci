def to_int(text: str) -> int:
    return int(text)


n = to_int("9007199254740993")
big = 2 ** 53 + 1
print("literal", big == float(big))
print("exact", 2 ** 53 == float(2 ** 53))
print("text", n == float(n))
print("small", 3 == 3.0)
print("ne", big != float(big))
