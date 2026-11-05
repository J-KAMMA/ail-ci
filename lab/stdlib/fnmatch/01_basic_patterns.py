import fnmatch


def main():
    names = ["readme.txt", "readme.md", "a.txt", "b.txt", "notes"]
    patterns = ["*.txt", "readme.*", "?.txt", "*", "a*", "*.tx?"]
    for pat in patterns:
        hits = [name for name in names if fnmatch.fnmatch(name, pat)]
        print(pat, hits)
    print(fnmatch.fnmatch("README.TXT", "*.txt"))
    print(fnmatch.fnmatchcase("README.TXT", "*.txt"))
    print(fnmatch.fnmatchcase("README.TXT", "*.TXT"))


main()
