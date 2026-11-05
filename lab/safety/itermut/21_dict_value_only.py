d: dict[str, int] = {"a": 1, "b": 2, "c": 3}
visited: list[str] = []
for k in d:
    visited.append(k)
    d[k] = d[k] + 10
print("visited", visited)
print("final", d)
