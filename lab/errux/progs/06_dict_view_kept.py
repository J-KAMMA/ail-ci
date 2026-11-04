# line: 4
# names: dict view
d = {"a": 1}
v = d.items()
d["b"] = 2
print(list(v))
