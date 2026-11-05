xs: list[int] = list(range(100000))
visited: list[int] = []
steps = 0
for x in xs:
    steps += 1
    if steps > 50:
        break
    visited.append(x)
    xs.append(x)
print("visited_count", len(visited))
print("visited_head", visited[:5])
print("final_len", len(xs))
print("final_tail", xs[-3:])
