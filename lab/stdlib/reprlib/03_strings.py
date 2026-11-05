import reprlib


def main():
    text = "abcdefghijklmnopqrstuvwxyz0123456789"
    print(reprlib.repr(text))
    print(reprlib.repr("short"))
    print(reprlib.repr(""))
    print(reprlib.repr("with 'quote' and \"double\""))
    print(reprlib.repr("line\nbreak\ttab"))
    print(reprlib.repr(["one", "two", "three", "four", "five", "six", "seven"]))
    print(reprlib.repr({"key": "a very long value that goes past the limit"}))


main()
