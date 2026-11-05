counts = {"a": 1}
view = counts.items()
counts["b"] = 2
print(list(view))
