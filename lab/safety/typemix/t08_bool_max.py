def to_int(text: str) -> int:
    return int(text)


n = to_int("1")
print("max_mixed", max(1, True))
print("min_mixed", min(0, False))
print("max_list", max([True, 2, False]))
print("text", max(n, True))
print("pair", max(True, False))
