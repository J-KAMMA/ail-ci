xs: list[int] = [2, 4, 6, 8]
print("start", xs, len(xs))
del xs[1]
print("after", xs, "len", len(xs))
last: int = xs[-1]
print("last", last)
print("head", xs[0])
del xs[len(xs)]
print("never", xs)
