d: dict[str, int] = {"a": 1, "b": 2, "c": 3}
visited: list[str] = []
steps = 0
try:
    for k in d:
        steps += 1
        if steps > 50:
            break
        visited.append(k)
        del d[k]
finally:
    print("visited", visited)
    print("final", d)
