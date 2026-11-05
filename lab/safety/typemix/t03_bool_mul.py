def to_int(text: str) -> int:
    return int(text)


n = to_int("3")
print("true_times", True * 3)
print("false_times", False * 3)
print("text_times", to_int("1") * n)
print("bool_bool", True * True)
print("negative", -True * 2)
