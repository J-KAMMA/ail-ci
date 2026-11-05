import fnmatch


def main():
    values = ["Foo.TXT", "foo.txt", "FOO.TXT", "foo.Txt"]
    for value in values:
        print(value, fnmatch.fnmatch(value, "foo.txt"),
              fnmatch.fnmatchcase(value, "foo.txt"))
    print("normcase identity", "Foo.TXT" == "Foo.TXT")
    paths = ["src/main.py", "src/lib.py", "tests/test_main.py", ".hidden"]
    print(fnmatch.filter(paths, "src/*.py"))
    print(fnmatch.filter(paths, "*.py"))
    print(fnmatch.fnmatchcase(".hidden", "*"))
    print(fnmatch.fnmatchcase(".hidden", ".*"))


main()
