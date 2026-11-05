xs: list[int] = [10, 20, 30]
print("start", xs, len(xs))
value: int = xs.pop(1)
print("popped", value, "left", xs, len(xs))
print("last", xs.pop())
print("left after", xs, len(xs))
xs.append(40)
print("appended", xs)
print("pop past", xs.pop(len(xs)))
