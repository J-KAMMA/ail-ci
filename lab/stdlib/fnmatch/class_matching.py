import fnmatch


def main():
    checks = [
        ("a", "[abc]"),
        ("d", "[abc]"),
        ("d", "[!abc]"),
        ("-", "[-a]"),
        ("a", "[a-]"),
        ("z", "[a-z]"),
        ("Z", "[A-Z]"),
        ("5", "[0-9]"),
        ("x", "[a-c]"),
        ("]", "[]]"),
        ("b", "[]a]"),
        ("!", "[!a]"),
        ("a", "[^a]"),
        ("^", "[^a]"),
        ("*", "[*]"),
        ("?", "[?]"),
        ("\\", "[\\]"),
        ("-", "[a-z-]"),
        ("_", "[!a-z]"),
        ("a", "[a-a]"),
    ]
    for name, pattern in checks:
        print(repr(name), pattern, fnmatch.fnmatchcase(name, pattern))
    names = ["x1", "x2", "xa", "x-", "x]", "x!", "x^", "x."]
    print("digits", fnmatch.filter(names, "x[0-9]"))
    print("not digit", fnmatch.filter(names, "x[!0-9]"))
    print("many", fnmatch.filter(names, "x[0-9a-]"))
    print("bracket", fnmatch.filter(names, "x[]]"))


main()
