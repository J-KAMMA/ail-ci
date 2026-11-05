def edges(xs: list[int]) -> tuple[int, int]:
    return xs[0], xs[-1]


xs: list[int] = [10, 20, 30]
first, last = edges(xs)
print("edges", first, last)
print("size", len(xs))
print("head", xs[-len(xs)])
print(xs[-len(xs) - 1])
