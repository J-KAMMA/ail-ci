scores: dict[str, int] = {"ada": 10, "bob": 20}
print("ada", scores["ada"], "count", len(scores))
print("bob", scores.get("bob"))
print("known", "bob" in scores)
print(scores["carol"])
