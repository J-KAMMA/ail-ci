def to_bool(text: str) -> bool:
    return text == "yes"


flag = to_bool("no")
print("abs_true", abs(True))
print("abs_false", abs(False))
print("abs_neg", abs(-True))
print("text_abs", abs(flag))
print("sum", abs(True) + abs(False))
