d: dict[str, int] = {"a": 1, "b": 2}
visited: list[str] = []
steps = 0
try:
    for k in d:
        steps += 1
        if steps > 50:
            break
        visited.append(k)
        value = d.pop(k)
        d[k] = value
finally:
    print("visited", visited)
    print("final", d)
