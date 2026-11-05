xs: list[int] = [1, 2, 3]
ys: list[int] = [10, 20, 30]
visited: list[int] = []
for a, b in zip(xs, ys):
    visited.append(a * 100 + b)
    if a == 1:
        xs.append(99)
print("visited", visited)
print("final_xs", xs)
print("final_ys", ys)
