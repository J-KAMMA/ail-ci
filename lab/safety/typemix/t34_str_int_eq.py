def to_int(text: str) -> int:
    return int(text)


n = to_int("0")
print("eq", "1" == 1)
print("ne", "1" != 1)
print("bool_empty", bool(""))
print("bool_zero", bool("0"))
print("text", bool(n))
print("str_true", bool("False"))
