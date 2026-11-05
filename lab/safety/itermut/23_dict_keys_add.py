d: dict[str, int] = {"a": 1, "b": 2}
visited: list[str] = []
steps = 0
try:
    for k in d.keys():
        steps += 1
        if steps > 50:
            break
        visited.append(k)
        d["y" + k] = 7
finally:
    print("visited", visited)
    print("final", d)
