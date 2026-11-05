word: str = "bounds"
print("all", word)
print("found", word.index("nd"), "size", len(word))
print("safe", "nd" in word)
print("start", word.index("b"))
print("rfind", word.rfind("nd"))
print("count", word.count("n"))
print(word.index("zz"))
