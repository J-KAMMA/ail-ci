xs: list[int] = [10, 20, 30, 40, 50, 60]
visited: list[int] = []
for x in xs:
    visited.append(x)
    if len(xs) > 0:
        xs.pop(0)
print("visited", visited)
print("final", xs)
