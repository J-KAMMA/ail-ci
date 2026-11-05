def number(text: str) -> float:
    return float(text)


print("prefix", number("2.5"))
print("scientific", number("1e3"))
print("next", number("abc"))
