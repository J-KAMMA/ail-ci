import fnmatch


def main():
    cases = [
        (b"readme.txt", b"*.txt"),
        (b"readme.txt", b"*.md"),
        (b"a1", b"a?"),
        (b"abc", b"a*c"),
        (b"data-7.bin", b"data-[0-9].bin"),
    ]
    for name, pat in cases:
        print(name, pat, fnmatch.fnmatchcase(name, pat))
    print(fnmatch.fnmatch(b"UPPER.TXT", b"*.txt"))


main()
