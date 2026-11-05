xs: list[int] = [1, 2, 3]
it = iter(xs)
visited: list[int] = []
steps = 0
for x in it:
    steps += 1
    if steps > 50:
        break
    visited.append(x)
    xs.append(x + 10)
print("visited", visited)
print("final_len", len(xs))
print("final_tail", xs[-6:])
