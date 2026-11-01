import fnmatch


def pick(names, patterns):
    chosen = []
    for pattern in patterns:
        for name in fnmatch.filter(names, pattern):
            if name not in chosen:
                chosen.append(name)
    return chosen


def main():
    names = [
        "app-1.4.2.tar.gz",
        "app-1.4.2.tar.gz.sha256",
        "app-1.4.2-py3-none-any.whl",
        "README.md",
        "CHANGELOG",
        "docs/app-1.4.2.pdf",
        "app-debug.tar.gz",
    ]
    print("dist:", pick(names, ["*.tar.gz", "*.whl"]))
    print("docs:", pick(names, ["*.md", "*.pdf", "CHANGELOG"]))
    print("checksums:", fnmatch.filter(names, "*sha256"))
    print("app:", fnmatch.filter(names, "app-*"))
    print("empty:", fnmatch.filter(names, "*.zip"))
    for name in names:
        print(name, fnmatch.fnmatch(name, "app-1.4.*"), fnmatch.fnmatchcase(name, "*.tar.gz"))


main()
