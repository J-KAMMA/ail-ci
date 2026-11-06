def to_bool(text: str) -> bool:
    return text == "yes"


items = ["a", "b", "c"]
flag = to_bool("yes")
print("true", [10, 20][True])
print("false", (10, 20)[False])
print("text", items[flag])
print("str", "xyz"[False])
print("nested", [[1], [2]][to_bool("no")])
