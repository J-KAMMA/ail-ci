import reprlib


def main():
    text = "abcdefghijklmnopqrstuvwxyz0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ"
    print("long", reprlib.repr(text))
    print("short", reprlib.repr("short"))
    print("empty", reprlib.repr(""))
    print("quote", reprlib.repr("it's a long string with a quote and a \\ backslash 1234567890"))
    r = reprlib.Repr()
    r.maxstring = 20
    print("maxstring 20", r.repr(text))
    r.maxstring = 10
    print("maxstring 10", r.repr(text))
    r.maxstring = 5
    print("maxstring 5", r.repr(text))
    r.maxstring = 3
    print("maxstring 3", r.repr(text))
    print("unicode", reprlib.repr("caf\u00e9 " * 12))


main()
