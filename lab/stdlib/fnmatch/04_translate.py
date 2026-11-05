import fnmatch


def main():
    patterns = ["*.txt", "a?c", "[a-c]x", "[!0-9]", "[]]", "[abc", "*.*", "a**b"]
    for pat in patterns:
        print(pat, "->", fnmatch.translate(pat))
    pattern = fnmatch.translate("file-[0-9].dat")
    print(pattern[:20])
    print(pattern[-4:])


main()
