xs: list[int] = [1, 2, 3]
visited: list[int] = []
for x in reversed(xs):
    visited.append(x)
    xs.append(0)
print("visited", visited)
print("final", xs)
