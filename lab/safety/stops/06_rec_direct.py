def countdown(n: int) -> int:
    return countdown(n + 1)


print("prefix", 10)
print("start", countdown(0))
print("unreachable", 1)
