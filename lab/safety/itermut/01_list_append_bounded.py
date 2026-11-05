xs: list[int] = [1, 2, 3]
visited: list[int] = []
steps = 0
for x in xs:
    steps += 1
    if steps > 50:
        break
    visited.append(x)
    if len(xs) < 8:
        xs.append(x * 10)
print("visited", visited)
print("final", xs)
