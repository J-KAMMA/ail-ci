def to_bool(text: str) -> bool:
    return text == "yes"


flag = to_bool("yes")
print("is_int", isinstance(True, int))
print("is_bool", isinstance(True, bool))
print("text", isinstance(flag, int))
print("float", isinstance(True, float))
print("type_name", type(True).__name__)
