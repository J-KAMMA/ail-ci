xs: list[int] = [5, 3, 1, 4, 2]
visited: list[int] = []
for x in xs:
    visited.append(x)
    xs.sort()
print("visited", visited)
print("final", xs)
