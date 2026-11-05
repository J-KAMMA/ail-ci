xs: list[int] = [2, 4, 6, 8]
del xs[1]
print("after", xs, "len", len(xs))
last: int = xs[-1]
print("last", last)
del xs[len(xs)]
print("never", xs)
