scores: dict[str, int] = {"ada": 10, "bob": 20}
print("ada", scores["ada"], "count", len(scores))
print("keys", sorted(scores))
print("bob", scores.get("bob"))
print("missing safe", scores.get("carol", -1))
print("known", "bob" in scores)
print("size", len(scores))
print(scores["carol"])
