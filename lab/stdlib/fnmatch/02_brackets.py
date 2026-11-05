import fnmatch


def main():
    cases = [
        ("a", "[a-c]"),
        ("d", "[a-c]"),
        ("c", "[!ab]"),
        ("a", "[!ab]"),
        ("]", "[]]"),
        ("x", "[]]"),
        ("[", "["),
        ("[abc", "[abc"),
        ("b", "[abc"),
        ("-", "[a-]"),
        ("5", "[0-9]"),
        ("z", "[0-9]"),
    ]
    for name, pat in cases:
        print(repr(name), repr(pat), fnmatch.fnmatchcase(name, pat))


main()
