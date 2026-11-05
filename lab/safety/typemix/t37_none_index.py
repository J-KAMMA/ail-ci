def to_int(text: str) -> int:
    return int(text)


n = to_int("1")
values = [None, n]
print("index_true", [None, 1].index(1))
print("index_none", [None, 1].index(None))
print("text", values.index(n))
print("count", values.count(None))
print("index_missing", values.index(2))
