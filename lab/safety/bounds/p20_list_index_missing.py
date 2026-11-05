xs: list[int] = [5, 10, 15]
print("all", xs)
print("found", xs.index(10), "size", len(xs))
print("safe", 10 in xs)
print("first", xs.index(5))
print("last index", xs.index(15))
print("missing safe", 99 in xs)
print(xs.index(99))
