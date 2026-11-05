def to_bool(text: str) -> bool:
    return text == "yes"


pairs = ["yes", "no", "yes"]
values = [to_bool(pairs[0]), to_bool(pairs[1]), to_bool(pairs[2])]
print("literal", sum([True, False, True]))
print("empty", sum([]))
print("from_text", sum(values))
print("start", sum(values, 10))
