xs: list[int] = [1, 2, 3]
visited: list[int] = []
for x in xs:
    visited.append(x)
    if len(xs) == 3:
        xs += xs
print("visited", visited)
print("final", xs)
