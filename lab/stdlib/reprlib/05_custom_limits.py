import reprlib


def main():
    values = list(range(10))
    custom = reprlib.Repr()
    custom.maxlist = 3
    custom.maxstring = 8
    custom.maxlevel = 2
    print(custom.repr(values))
    print(custom.repr([values, values]))
    print(custom.repr("abcdefghijklmno"))
    text = reprlib.Repr(maxlist=2, maxstring=5, fillvalue="<...>")
    print(text.repr(values))
    print(text.repr("abcdefghij"))
    print(reprlib.repr(values))


main()
