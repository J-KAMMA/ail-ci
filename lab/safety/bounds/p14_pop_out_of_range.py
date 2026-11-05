xs: list[int] = [10, 20, 30]
value: int = xs.pop(1)
print("popped", value, "left", xs, len(xs))
print("last", xs.pop())
print("pop past", xs.pop(len(xs)))
