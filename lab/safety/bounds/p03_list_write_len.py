def append_one(xs: list[int], value: int) -> int:
    xs.append(value)
    return len(xs)


xs: list[int] = [1, 2, 3]
print("size", append_one(xs, 4))
print("before", xs)
xs[len(xs)] = 99
print("never", xs)
