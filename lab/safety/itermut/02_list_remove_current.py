xs: list[int] = [1, 2, 3, 4, 5, 6]
visited: list[int] = []
for x in xs:
    visited.append(x)
    xs.remove(x)
print("visited", visited)
print("final", xs)
