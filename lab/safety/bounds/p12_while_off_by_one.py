xs: list[int] = [3, 1, 4]
i: int = 0
total: int = 0
while i < len(xs):
    total += xs[i]
    i += 1
print("total", total, "i", i)

i = 0
while i <= len(xs):
    total += xs[i]
    i += 1
print("never", total)
