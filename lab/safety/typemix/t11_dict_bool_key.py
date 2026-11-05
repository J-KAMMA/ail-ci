def to_int(text: str) -> int:
    return int(text)


d = {1: "a", True: "b", 1.0: "c"}
print("len", len(d))
print("lookup_int", d[1])
print("lookup_true", d[True])
print("lookup_float", d[1.0])
key = to_int("1")
print("from_text", d[key])
