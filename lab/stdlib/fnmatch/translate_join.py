import fnmatch


def main():
    patterns = ["*.py", "*.txt", "test_*"]
    translated = []
    for pattern in patterns:
        translated.append(fnmatch.translate(pattern))
    print(translated)
    print("joined", "|".join(translated))
    names = ["main.py", "notes.txt", "test_one", "other.md"]
    for name in names:
        hits = []
        for pattern in patterns:
            if fnmatch.fnmatchcase(name, pattern):
                hits.append(pattern)
        print(name, hits)
    print("unique", len(set(translated)))
    print("literal join", "|".join(fnmatch.translate(p) for p in ["a", "b"]))
    print("count", len(fnmatch.filter(names, "[a-z]*")))
    print("translate class", fnmatch.translate("[a-c]?"))


main()
