from collections import Counter


def main() -> int:
    empty: Counter[str] = Counter()
    print(empty.most_common(), empty.most_common(0), empty.most_common(-1))
    print(empty.total(), len(empty), list(empty.elements()))
    text = Counter("abca")
    print(text["a"], text["z"], len(text))
    text["z"] += 1
    print(text)
    text.subtract("abc")
    print(text)
    text.subtract({"a": 5})
    print(sorted(text.items()))
    text.update({"a": 10, "b": 2})
    text.update("cab")
    print(text)
    letters = Counter(c for c in "mississippi")
    vowels = Counter("aeiou")
    print(sorted((letters - vowels).items()))
    print(sorted((letters & vowels).items()))
    print(sorted((letters | vowels).items()))
    pairs = Counter(zip("aabbc", "xyxyz"))
    print(pairs)
    print(pairs.most_common(2))
    pairs.update([("a", "x"), ("q", "r")])
    print(pairs)
    words = Counter(["one", "two", "one"])
    print(words + Counter(), words - Counter(), words & Counter(), words | Counter())
    return 0


main()
