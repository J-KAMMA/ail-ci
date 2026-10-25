d = {"a": 1.5, "b": 2.25}

def first() -> float:
    return d["a"]

def scale(k: str) -> float:
    return d[k] * 2.0

print(first(), scale("b"), d["a"] + d["b"])
