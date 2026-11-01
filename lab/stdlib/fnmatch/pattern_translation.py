import fnmatch


def main():
    patterns = [
        "",
        "*",
        "*.py",
        "file?.txt",
        "[abc].log",
        "[!abc].log",
        "[a-z0-9]",
        "a*b*c",
        "**",
        "a[b",
        "a]b",
        "[!]",
        "[]]",
        "[-a]",
        "[a-]",
        r"a\b",
    ]
    for pattern in patterns:
        print(repr(pattern), fnmatch.translate(pattern))
    print("round trip", fnmatch.fnmatch("file1.txt", "file?.txt"))
    print("literal star", fnmatch.fnmatch("a*b", r"a\*b"))
    print("empty match", fnmatch.fnmatch("", ""), fnmatch.fnmatch("x", ""))
    print("translate empty", fnmatch.translate(""))


main()
