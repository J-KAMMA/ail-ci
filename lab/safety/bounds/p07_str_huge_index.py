def char_at(text: str, i: int) -> str:
    return text[i]


word: str = "bounds"
print("word", word, "len", len(word))
print("ok", char_at(word, 2))
print("last", word[-1])
print("huge", char_at(word, 2 ** 40))
