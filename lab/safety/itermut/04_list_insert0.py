xs: list[int] = [1, 2, 3]
visited: list[int] = []
steps = 0
for x in xs:
    steps += 1
    if steps > 50:
        break
    visited.append(x)
    xs.insert(0, 0)
print("visited", visited)
print("final_len", len(xs))
print("final", xs)
