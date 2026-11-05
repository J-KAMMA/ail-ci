def descend(n: int) -> int:
    if n == 0:
        return 0
    return descend(n - 1)


print("prefix", descend(10))
print("start", descend(5000))
print("unreachable", 1)
