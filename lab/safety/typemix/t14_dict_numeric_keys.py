def to_int(text: str) -> int:
    return int(text)


values = ["2", "2"]
d = {2: "int", 2.0: "float", True: "bool"}
print("len", len(d))
print("get_int", d[2])
print("get_float", d[2.0])
print("get_key", d[to_int(values[0])])
print("true", d[True])
