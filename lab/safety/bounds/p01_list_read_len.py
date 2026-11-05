def total(xs: list[int]) -> int:
    acc = 0
    for x in xs:
        acc += x
    return acc


xs: list[int] = [4, 8, 15]
print("total", total(xs))
print("len", len(xs))
print("last", xs[len(xs) - 1])
print(xs[len(xs)])
