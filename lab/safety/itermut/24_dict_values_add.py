d: dict[str, int] = {"a": 1, "b": 2}
visited: list[int] = []
steps = 0
try:
    for v in d.values():
        steps += 1
        if steps > 50:
            break
        visited.append(v)
        d["z" + str(steps)] = v + 10
finally:
    print("visited", visited)
    print("final", d)
