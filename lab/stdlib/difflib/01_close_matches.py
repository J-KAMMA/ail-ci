import difflib


def suggest(word, vocabulary):
    return difflib.get_close_matches(word, vocabulary, n=3, cutoff=0.6)


def main():
    vocabulary = ["accept", "except", "expect", "excerpt", "access", "excess"]
    for word in ["accept", "exept", "exces", "xyz"]:
        matches = suggest(word, vocabulary)
        if matches:
            print(word, "->", ", ".join(matches))
        else:
            print(word, "-> (no suggestion)")
    print(difflib.get_close_matches("recieve", vocabulary, n=1))
    print(difflib.get_close_matches("exces", vocabulary, cutoff=0.9))
    try:
        difflib.get_close_matches("a", vocabulary, n=0)
    except ValueError as exc:
        print("error:", exc)
    try:
        difflib.get_close_matches("a", vocabulary, cutoff=1.5)
    except ValueError as exc:
        print("error:", exc)


main()
