from operator import methodcaller


def main() -> int:
    raw = ["  pear ", " Apple", "banana  ", "  cherry"]
    print("stripped")
    for text in sorted(raw, key=methodcaller("strip")):
        print(repr(text.strip()))
    replacer = methodcaller("replace", "a", "A")
    print("replaced")
    for word in ("banana", "apple", "fig"):
        print(replacer(word))
    upper = methodcaller("upper")
    print("upper order")
    for word in sorted(["beta", "Alpha", "gamma"], key=upper):
        print(word, upper(word))
    splitter = methodcaller("split", ",")
    for line in ("a,b,c", "one,two", "solo"):
        print(splitter(line))
    padded = methodcaller("rjust", 6, ".")
    for word in ("a", "abc", "hello"):
        print(padded(word))
    return 0


main()
