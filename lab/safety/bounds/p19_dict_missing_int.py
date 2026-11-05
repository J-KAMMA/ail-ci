scores: dict[int, int] = {1: 10, 2: 20}
print("one", scores[1], "size", len(scores))
print("keys", sorted(scores))
print("two", scores.get(2))
print("missing safe", scores.get(3, -1))
print("known", 2 in scores)
print("size", len(scores))
print(scores[3])
