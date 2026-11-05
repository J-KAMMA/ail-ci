d: dict[str, int] = {"a": 1, "b": 2}
visited: list[str] = []
steps = 0
try:
    for k, v in d.items():
        steps += 1
        if steps > 50:
            break
        visited.append(k)
        d["x" + k] = v + 10
finally:
    print("visited", visited)
    print("final", d)
