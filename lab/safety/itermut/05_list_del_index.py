xs: list[int] = [1, 2, 3, 4, 5, 6]
visited: list[int] = []
i = 0
for x in xs:
    visited.append(x)
    if x % 2 == 0:
        del xs[i]
    i += 1
print("visited", visited)
print("final", xs)
