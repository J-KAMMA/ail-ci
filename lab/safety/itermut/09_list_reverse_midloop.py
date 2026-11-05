xs: list[int] = [1, 2, 3, 4, 5]
visited: list[int] = []
for x in xs:
    visited.append(x)
    xs.reverse()
print("visited", visited)
print("final", xs)
