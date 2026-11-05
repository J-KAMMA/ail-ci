import reprlib


def main():
    small = 12345
    big = 10 ** 30
    huge = 123456789012345678901234567890
    print(reprlib.repr(small))
    print(reprlib.repr(big))
    print(reprlib.repr(huge))
    print(reprlib.repr(-huge))
    print(reprlib.repr([big, huge, small]))
    print(reprlib.aRepr.maxlong)


main()
