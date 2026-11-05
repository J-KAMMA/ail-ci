def third(t: tuple[int, int, int]) -> int:
    return t[2]


t: tuple[int, int, int] = (7, 8, 9)
print("sum", sum(t), "third", third(t))
print("len", len(t))
print(t[len(t)])
