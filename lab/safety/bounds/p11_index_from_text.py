text: str = "12"
xs: list[str] = ["a", "b", "c"]
i: int = int(text)
print("parsed", i, "size", len(xs))
print("ok", xs[i - 10])
print("parsed again", i)
print("text len", len(text))
print(xs[i])
