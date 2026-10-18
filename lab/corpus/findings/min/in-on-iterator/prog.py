def sub(s: str, t: str) -> bool:
    it = iter(s)
    return all(ch in it for ch in t)

print(sub("abcde", "ace"), sub("abc", "ba"))
