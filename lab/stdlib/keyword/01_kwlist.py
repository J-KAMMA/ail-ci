import keyword


def main() -> None:
    words = list(keyword.kwlist)
    print("count", len(words))
    print("first", words[0])
    print("last", words[-1])
    print("all", words)
    ordered = True
    for i in range(1, len(words)):
        if words[i - 1] > words[i]:
            ordered = False
    print("sorted", ordered)
    print("has def", "def" in words)
    print("has match", "match" in words)


main()
