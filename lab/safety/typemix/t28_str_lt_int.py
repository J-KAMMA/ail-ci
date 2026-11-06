def to_int(text: str) -> int:
    return int(text)


n = to_int("4")
print("prefix", "3" == "3")
print("suffix", "abc" < "abd")
print("text", "10" < "9")
print("next", "3" < n)
