import fnmatch


def main():
    names = ["alpha", "beta", "", "a b", "a\tb", "line\nbreak"]
    for pattern in ["", "*", "?", "a b", "a\tb", "line*break", "*\n*"]:
        try:
            print(repr(pattern), fnmatch.filter(names, pattern))
        except Exception as exc:
            print(repr(pattern), type(exc).__name__, str(exc))
    for value in [None, 7, ["x"]]:
        try:
            print("value", value, fnmatch.fnmatch(value, "*"))
        except Exception as exc:
            print("value", type(value).__name__, type(exc).__name__, str(exc))
    for pattern in [None, 7, ["x"]]:
        try:
            print("pattern", pattern, fnmatch.fnmatch("x", pattern))
        except Exception as exc:
            print("pattern", type(pattern).__name__, type(exc).__name__, str(exc))
    try:
        fnmatch.filter(None, "*")
    except Exception as exc:
        print("filter", type(exc).__name__, str(exc))


main()
