def to_int(text: str) -> int:
    return int(text)


n = to_int("2")
values = [3, 1.5, True, n]
print("literal", sorted([3, 1.5, True, 2]))
print("text", sorted(values))
print("min", min(values))
print("max", max(values))
print("reversed", sorted([3, 1.5, True, 2], reverse=True))
