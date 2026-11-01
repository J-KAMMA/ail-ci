import operator


def main() -> int:
    scores = [88, 92, 88, 75, 92, 88]
    print(operator.contains(scores, 92))
    print(operator.contains(scores, 100))
    print(operator.countOf(scores, 88))
    print(operator.indexOf(scores, 75))
    text = "the quick brown fox jumps over the lazy dog"
    print(operator.contains(text, "fox"))
    print(operator.contains(text, "cat"))
    print(operator.countOf(text, "o"))
    print(operator.indexOf(text, "b"))
    print(operator.countOf(text, "th"))
    try:
        print(operator.indexOf(text, "brown"))
    except ValueError as error:
        print("substring", type(error).__name__, error)
    pairs = (("a", 1), ("b", 2), ("a", 3))
    print(operator.countOf(pairs, ("a", 1)))
    print(operator.indexOf(pairs, ("b", 2)))
    empty = []
    print(operator.contains(empty, 1), operator.countOf(empty, 1))
    try:
        operator.indexOf(scores, 60)
    except ValueError as error:
        print("absent", type(error).__name__, error)
    return 0


main()
