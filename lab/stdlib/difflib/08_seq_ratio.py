import difflib


def main():
    pairs = [
        ("abcd", "bcde"),
        ("private Thread currentThread;", "private volatile Thread currentThread;"),
        ("", ""),
        ("abc", ""),
        ("aaaa", "bbbb"),
        ([1, 2, 3, 4], [1, 3, 4, 5]),
    ]
    for left, right in pairs:
        matcher = difflib.SequenceMatcher(None, left, right)
        print(repr(left), repr(right))
        print(" ratios:", matcher.ratio(), matcher.quick_ratio(), matcher.real_quick_ratio())
    matcher = difflib.SequenceMatcher(a="one two", b="one too")
    print("keyword ratio:", matcher.ratio())
    matcher.set_seq2("one two three")
    for candidate in ["one two", "two three", "none"]:
        matcher.set_seq1(candidate)
        print(candidate, round(matcher.ratio(), 4), round(matcher.quick_ratio(), 4))
    empty = difflib.SequenceMatcher()
    print("empty:", empty.ratio(), empty.quick_ratio(), empty.real_quick_ratio())


main()
