s: set[int] = {1, 2, 3}
visited: list[int] = []
steps = 0
try:
    for x in s:
        steps += 1
        if steps > 50:
            break
        visited.append(x)
        s.add(x + 10)
finally:
    print("visited", visited)
    print("final", sorted(s))
