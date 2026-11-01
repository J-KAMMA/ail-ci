import fnmatch

IGNORE = ["*.o", "*.obj", "*.pyc", "__pycache__", "build/*", "*.tmp"]


def ignored(path):
    for pattern in IGNORE:
        if fnmatch.fnmatchcase(path, pattern):
            return pattern
    return ""


def main():
    paths = [
        "src/main.o",
        "src/main.c",
        "src/module.pyc",
        "__pycache__",
        "build/lib/app.so",
        "build/notes.txt",
        "dist/app.tar",
        "scratch.tmp",
        "src/clean.py",
    ]
    kept = []
    for path in paths:
        reason = ignored(path)
        if reason == "":
            kept.append(path)
        else:
            print("drop", path, "by", reason)
    print("kept", len(kept))
    for path in kept:
        print("keep", path)
    print("objects", len(fnmatch.filter(paths, "*.o")))
    print("under build", len(fnmatch.filter(paths, "build/*")))
    print("sources", fnmatch.filter(paths, "*.py"))


main()
