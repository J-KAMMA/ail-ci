def to_int(text: str) -> int:
    return int(text)


s = {0, False, 0.0, -0.0}
print("len", len(s))
print("zero_in", 0 in s, False in s, 0.0 in s)
more = set([to_int("0"), False])
print("more", len(more))
print("union", len(s | more))
