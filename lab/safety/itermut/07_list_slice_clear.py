xs: list[int] = [1, 2, 3, 4]
visited: list[int] = []
for x in xs:
    visited.append(x)
    xs[:] = []
print("visited", visited)
print("final", xs)
