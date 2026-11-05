def pick(xs: list[str], i: int) -> str:
    return xs[i]


words: list[str] = ["alpha", "beta"]
print("pick", pick(words, 1))
print("size", len(words))
print("safe", pick(words, 0))
print(pick(words, len(words)))
