def to_int(text: str) -> int:
    return int(text)


n = to_int("1")
print("eq", None == n)
print("ne", None != n)
print("list", [None, 1])
print("next", None < n)
